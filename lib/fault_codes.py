# ================================================================
#  fault_codes.py  —  Gear IQ OEM Fault Code Detection Engine
#
#  Two types:
#    DIRECT     — single sensor threshold breach
#    INFERRED   — cross-sensor correlation
# ================================================================

from datetime import datetime, timezone, timedelta
from constants import FAULT_CATALOG, THRESHOLDS

IST = timezone(timedelta(hours=5, minutes=30))


# ════════════════════════════════════════════════════════════════
#  FAULT DETECTION ENGINE
# ════════════════════════════════════════════════════════════════

def detect_faults(vib_data: dict, volt_data: list, temp_data: list = None) -> list:
    """
    Run all fault checks against latest sensor readings.

    Args:
        vib_data  : latest vibration record  { total_vibration, temperature, current, ... }
        volt_data : latest voltage records   [{ sensor_id, voltage, current, power, ... }]
        temp_data : latest temperature data  [{ sensor_id, temperature, ... }]  (optional)

    Returns:
        List of active fault dicts
    """
    faults  = []
    T       = THRESHOLDS
    now_ist = datetime.now(IST).strftime('%I:%M %p')

    # ── Aggregate sensor values ──────────────────────────────────
    motor_temp    = float(vib_data.get('temperature',    0)) if vib_data else 0
    motor_vib     = float(vib_data.get('total_vibration',0)) if vib_data else 0
    motor_current = float(vib_data.get('current',        0)) if vib_data else 0
    motor_online  = vib_data.get('status') == 'online' if vib_data else False

    cell_voltages = [float(r.get('voltage', 0)) for r in volt_data] if volt_data else []
    total_current = sum(float(r.get('current', 0)) for r in volt_data) if volt_data else 0
    avg_voltage   = sum(cell_voltages) / len(cell_voltages) if cell_voltages else 0
    bat_soc       = max(0, min(100, ((avg_voltage - 11.8) / (12.6 - 11.8)) * 100))

    def add_fault(code, value_str):
        info = FAULT_CATALOG[code]
        faults.append({
            'code':     code,
            'type':     info['type'],
            'severity': info['severity'],
            'oem_desc': info['oem_desc'],
            'gear_iq':  info['gear_iq'],
            'sensor':   info['sensor'],
            'value':    value_str,
            'time':     now_ist,
        })

    # ════════════════════════════════════════════════════════════
    #  DIRECT DETECTION
    # ════════════════════════════════════════════════════════════

    # 1600 — Battery voltage too high
    for r in volt_data or []:
        v = float(r.get('voltage', 0))
        if v > T['voltage_high']:
            add_fault('1600', f'Cell B{r["sensor_id"]} = {v:.2f}V  (limit {T["voltage_high"]}V)')
            break

    # 2C00 — Battery voltage too low
    for r in volt_data or []:
        v = float(r.get('voltage', 0))
        if v > 0 and v < T['voltage_low']:
            add_fault('2C00', f'Cell B{r["sensor_id"]} = {v:.2f}V  (limit {T["voltage_low"]}V)')
            break
    if bat_soc < T['battery_soc_low'] and not any(f['code'] == '2C00' for f in faults):
        add_fault('2C00', f'SOC = {bat_soc:.0f}%  (limit {T["battery_soc_low"]}%)')

    # FFF6 — Battery over-current
    if total_current > T['battery_overcurrent']:
        add_fault('FFF6', f'Total current = {total_current:.1f}A  (limit {T["battery_overcurrent"]}A)')

    # FF31 — Motor over temperature
    if motor_temp > T['motor_temp_high']:
        add_fault('FF31', f'Motor temp = {motor_temp:.1f}°C  (limit {T["motor_temp_high"]}°C)')

    # FFFA — Armature overcurrent
    if motor_current > T['motor_overcurrent']:
        add_fault('FFFA', f'Motor current = {motor_current:.1f}A  (limit {T["motor_overcurrent"]}A)')

    # FFF7 — Field overcurrent (motor current > 80% of overcurrent threshold)
    if motor_current > T['motor_overcurrent'] * 0.8 and motor_current <= T['motor_overcurrent']:
        add_fault('FFF7', f'Motor current = {motor_current:.1f}A  (field winding pattern)')

    # FF10 — Armature open circuit (vibration detected but zero current)
    if motor_online and motor_vib > T['zero_current_vib'] and motor_current == 0:
        add_fault('FF10', f'Vib={motor_vib:.2f} mm/s but current=0A during operation')

    # FFF3 — Armature wiring fault (current erratic — negative or unexpected spike)
    if motor_current < 0:
        add_fault('FFF3', f'Motor current = {motor_current:.1f}A  (negative — erratic reading)')

    # ════════════════════════════════════════════════════════════
    #  INFERRED (CROSS-SENSOR CORRELATION)
    # ════════════════════════════════════════════════════════════

    # 4401 — Controller fault: vibration anomaly AND current anomaly together
    vib_anomaly = motor_vib > T['vibration_anomaly']
    cur_anomaly = motor_current > T['motor_overcurrent'] * 0.7
    if vib_anomaly and cur_anomaly:
        add_fault('4401', f'Vib={motor_vib:.2f} mm/s + Current={motor_current:.1f}A — simultaneous anomaly')

    # FF0B — Thermal foldback: temp is high AND current is unusually LOW
    #         (controller throttling power to protect from heat)
    temp_high    = motor_temp > T['motor_temp_high'] * 0.85       # 85% of trip threshold
    current_low  = 0 < motor_current < T['battery_overcurrent'] * 0.3
    if temp_high and current_low and motor_online:
        add_fault('FF0B', f'Temp={motor_temp:.1f}°C rising, Current={motor_current:.1f}A reducing — throttle signature')

    # 2F01 — Throttle displaced on startup: motor current zero on first readings after power-on
    #         (This would need startup flag — placeholder check: online but zero current + zero vib)
    if motor_online and motor_current == 0 and motor_vib == 0:
        add_fault('2F01', f'Motor online but current=0, vib=0 — startup baseline anomaly')

    return faults


# ════════════════════════════════════════════════════════════════
#  SUMMARY HELPER
# ════════════════════════════════════════════════════════════════

def fault_summary(faults: list) -> dict:
    critical = [f for f in faults if f['severity'] == 'CRITICAL']
    warning  = [f for f in faults if f['severity'] == 'WARNING']
    return {
        'total':    len(faults),
        'critical': len(critical),
        'warning':  len(warning),
        'status':   'CRITICAL' if critical else ('WARNING' if warning else 'NORMAL'),
        'faults':   faults,
    }