# ================================================================
#  KPI CALCULATION LOGIC  (add to api_server.py)
#  
#  Tables used:
#    vibration_sensor_data  → total_vibration, timestamp
#    voltage_data           → sensor_id, power, energy, timestamp
#
#  KPIs calculated:
#    operating_time  — hours vibration was above threshold
#    idle_time       — hours system was on but not operating
#    cycles_today    — count of distinct work cycles
#    energy_used     — kWh consumed (power × time integration)
# ================================================================

from datetime import datetime, date

from db import get_db_connection, DB_CONFIG

# ── Tunable thresholds ─────────────────────────────────────────
VIB_OPERATING_THRESHOLD = 0.3   # mm/s  — above this = "operating"
MIN_CYCLE_DURATION_SEC  = 30    # sec   — burst must last ≥ 30s to count as a cycle
SENSOR_TIMEOUT_SEC      = 30    # sec   — gap > 30s means sensor was offline (don't count)


# ─────────────────────────────────────────────────────────────────
#  CORE CALCULATION FUNCTION
# ─────────────────────────────────────────────────────────────────
def calculate_kpi_today():
    """
    Query today's sensor data and return KPI dictionary:
    {
        operating_time : float  (hours)
        idle_time      : float  (hours)
        cycles_today   : int
        energy_used    : float  (kWh)
    }
    """
    conn = get_db_connection()
    if not conn:
        return None

    cur = conn.cursor()
    today_start = datetime.combine(date.today(), datetime.min.time())

    # ── 1. VIBRATION READINGS FOR TODAY ───────────────────────
    cur.execute("""
        SELECT total_vibration, timestamp
        FROM   vibration_sensor_data
        WHERE  timestamp >= %s
        ORDER  BY timestamp ASC
    """, (today_start,))
    vib_rows = cur.fetchall()   # [(vib_float, datetime), ...]

    # ── 2. VOLTAGE / POWER READINGS FOR TODAY ─────────────────
    cur.execute("""
        SELECT sensor_id, power, energy, timestamp
        FROM   voltage_data
        WHERE  timestamp >= %s
        ORDER  BY sensor_id, timestamp ASC
    """, (today_start,))
    volt_rows = cur.fetchall()  # [(sensor_id, power, energy, datetime), ...]

    cur.close()
    conn.close()

    # ── 3. COMPUTE OPERATING TIME, IDLE TIME, CYCLES ──────────
    operating_sec = 0.0
    idle_sec      = 0.0
    cycles        = 0

    in_cycle      = False
    cycle_start   = None
    prev_ts       = None

    for vib, ts in vib_rows:
        if prev_ts is not None:
            gap_sec     = (ts - prev_ts).total_seconds()

            # Skip large gaps (sensor was offline / not recording)
            if gap_sec > SENSOR_TIMEOUT_SEC:
                # Close any open cycle without counting (data gap)
                if in_cycle:
                    in_cycle = False
                prev_ts = ts
                continue

            is_operating = vib > VIB_OPERATING_THRESHOLD

            if is_operating:
                operating_sec += gap_sec
                if not in_cycle:
                    # Vibration just crossed threshold → start of a new burst
                    in_cycle    = True
                    cycle_start = prev_ts
            else:
                idle_sec += gap_sec
                if in_cycle:
                    # Vibration dropped back down → end of burst
                    burst_duration = (ts - cycle_start).total_seconds()
                    if burst_duration >= MIN_CYCLE_DURATION_SEC:
                        cycles += 1          # count only meaningful bursts
                    in_cycle = False

        prev_ts = ts

    # Close any still-open cycle at the end of the data
    if in_cycle and cycle_start and prev_ts:
        burst_duration = (prev_ts - cycle_start).total_seconds()
        if burst_duration >= MIN_CYCLE_DURATION_SEC:
            cycles += 1

    # ── 4. COMPUTE ENERGY USED (power × time integration) ─────
    #
    #  Method: trapezoidal integration per sensor
    #  power  is in Watts, time interval in hours → result in Wh
    #  Divide by 1000 at the end to get kWh.
    #
    #  If your sensor stores CUMULATIVE energy (Wh meter style):
    #  → use the alternative method at the bottom of this file.
    #
    total_energy_wh  = 0.0
    sensor_prev      = {}   # {sensor_id: (power_W, timestamp)}

    for sensor_id, power, energy, ts in volt_rows:
        power = float(power or 0)

        if sensor_id in sensor_prev:
            prev_power, prev_ts = sensor_prev[sensor_id]
            gap_sec      = (ts - prev_ts).total_seconds()

            # Skip large gaps
            if gap_sec <= SENSOR_TIMEOUT_SEC:
                interval_hr  = gap_sec / 3600
                avg_power    = (power + prev_power) / 2   # trapezoidal rule
                total_energy_wh += avg_power * interval_hr

        sensor_prev[sensor_id] = (power, ts)

    total_energy_kwh = total_energy_wh / 1000

    return {
        'operating_time': round(operating_sec / 3600, 2),   # hours
        'idle_time':      round(idle_sec      / 3600, 2),   # hours
        'cycles_today':   cycles,
        'energy_used':    round(total_energy_kwh, 3)        # kWh
    }


# ─────────────────────────────────────────────────────────────────
#  FLASK ROUTE  — add this to api_server.py
# ─────────────────────────────────────────────────────────────────
# @app.route('/api/kpi')
# def kpi():
#     data = calculate_kpi_today()
#     if not data:
#         return jsonify({'operating_time': 0, 'idle_time': 0,
#                         'cycles_today': 0,   'energy_used': 0})
#     return jsonify(data)


# ─────────────────────────────────────────────────────────────────
#  ALTERNATIVE: CUMULATIVE ENERGY METER
#  Use this instead of the trapezoidal method if your voltage
#  sensor's "energy" column is a running Wh counter (like a
#  smart meter that keeps incrementing).
# ─────────────────────────────────────────────────────────────────
def energy_from_cumulative_meter(volt_rows):
    """
    If energy column = cumulative Wh counter per sensor:
    today's energy = last_value - first_value  per sensor, then sum.
    """
    sensor_first = {}
    sensor_last  = {}

    for sensor_id, power, energy, ts in volt_rows:
        energy = float(energy or 0)
        if sensor_id not in sensor_first:
            sensor_first[sensor_id] = energy
        sensor_last[sensor_id] = energy

    total_wh = sum(
        sensor_last[sid] - sensor_first[sid]
        for sid in sensor_last
    )
    return round(total_wh / 1000, 3)   # kWh


# ─────────────────────────────────────────────────────────────────
#  RAW SQL (PostgreSQL)  — run directly for debugging
# ─────────────────────────────────────────────────────────────────
"""
-- Operating time by bucket (1-minute intervals)
WITH buckets AS (
  SELECT
    date_trunc('minute', timestamp)  AS minute,
    MAX(total_vibration)             AS max_vib
  FROM vibration_sensor_data
  WHERE timestamp >= CURRENT_DATE
  GROUP BY 1
)
SELECT
  COUNT(*) FILTER (WHERE max_vib > 0.3) / 60.0  AS operating_hours,
  COUNT(*) FILTER (WHERE max_vib <= 0.3) / 60.0  AS idle_hours
FROM buckets;


-- Cycles today (count vibration bursts using LAG window function)
WITH states AS (
  SELECT
    timestamp,
    total_vibration > 0.3                         AS is_operating,
    LAG(total_vibration > 0.3) OVER (ORDER BY id) AS prev_operating
  FROM vibration_sensor_data
  WHERE timestamp >= CURRENT_DATE
)
SELECT COUNT(*) AS cycles_today
FROM states
WHERE is_operating = TRUE AND (prev_operating = FALSE OR prev_operating IS NULL);


-- Energy used today (integrate power × time per sensor, sum all)
WITH intervals AS (
  SELECT
    sensor_id,
    power,
    timestamp,
    LAG(power,     1) OVER w  AS prev_power,
    LAG(timestamp, 1) OVER w  AS prev_ts,
    EXTRACT(EPOCH FROM (timestamp - LAG(timestamp,1) OVER w)) AS gap_sec
  FROM voltage_data
  WHERE timestamp >= CURRENT_DATE
  WINDOW w AS (PARTITION BY sensor_id ORDER BY timestamp)
)
SELECT
  ROUND(
    SUM(
      CASE WHEN gap_sec <= 30                          -- skip offline gaps
           THEN ((power + prev_power) / 2.0)           -- avg power (W)
                * (gap_sec / 3600.0)                   -- × hours
           ELSE 0
      END
    ) / 1000.0,                                        -- Wh → kWh
    3
  ) AS energy_kwh
FROM intervals
WHERE prev_ts IS NOT NULL;
"""
