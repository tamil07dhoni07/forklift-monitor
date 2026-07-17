#!/usr/bin/env python3
# ================================================================
#  kpi_logic.py  —  Gear IQ KPI Calculations
# ================================================================

import logging
from datetime import datetime, date, timezone, timedelta
from db import get_db_connection

log = logging.getLogger('kpi_logic')

# ── Tunable constants ────────────────────────────────────────────
VIB_THRESHOLD      = 0.3    # mm/s — above = operating, below = idle
MIN_CYCLE_SECS     = 30     # sec  — burst must last ≥ 30s to count as cycle
SENSOR_TIMEOUT_SEC = 60     # sec  — gap larger than this = sensor was offline

IST = timezone(timedelta(hours=5, minutes=30))


def calculate_kpi_today():
    log.info('📊  calculate_kpi_today  →  starting ...')

    conn = get_db_connection()
    if not conn:
        log.error('📊  calculate_kpi_today  →  no DB connection')
        return None

    try:
        cur = conn.cursor()

        # ── Get today's date boundary in DB's timezone ───────────
        # Use DB current_date to avoid timezone mismatch
        cur.execute("SELECT CURRENT_DATE, NOW()")
        db_date, db_now = cur.fetchone()
        today_start = datetime.combine(db_date, datetime.min.time())

        log.debug(f'📊  DB date={db_date}  DB now={db_now}  today_start={today_start}')

        # ── Fetch today's vibration rows ─────────────────────────
        cur.execute("""
            SELECT total_vibration, timestamp
            FROM   vibration_sensor_data
            WHERE  timestamp >= %s
            ORDER  BY timestamp ASC
        """, (today_start,))
        vib_rows = cur.fetchall()

        log.info(f'📊  vibration rows today  →  {len(vib_rows)} records')

        if not vib_rows:
            log.warning('📊  NO vibration records found for today  →  KPI will be zero')
            log.warning(f'📊  Check: does vibration_sensor_data have rows with timestamp >= {today_start} ?')

            # ── Diagnostic: check latest row in DB ───────────────
            cur.execute("SELECT total_vibration, timestamp FROM vibration_sensor_data ORDER BY id DESC LIMIT 1")
            latest = cur.fetchone()
            if latest:
                log.warning(f'📊  Latest DB row: vib={latest[0]}  ts={latest[1]}')
            else:
                log.error('📊  vibration_sensor_data table is EMPTY')

            return {'operating_time': 0, 'idle_time': 0, 'cycles_today': 0, 'energy_used': 0}

        # ── Log sample of data ───────────────────────────────────
        log.debug(f'📊  first row: vib={vib_rows[0][0]}  ts={vib_rows[0][1]}')
        log.debug(f'📊  last  row: vib={vib_rows[-1][0]}  ts={vib_rows[-1][1]}')

        # ── Count operating/idle/cycles ──────────────────────────
        operating_sec = 0.0
        idle_sec      = 0.0
        cycles        = 0
        in_cycle      = False
        cycle_start   = None
        prev_ts       = None

        above_thresh  = 0   # debug counters
        below_thresh  = 0
        skipped_gaps  = 0

        for vib, ts in vib_rows:
            # Strip timezone info if present to compare consistently
            if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)

            vib_val = float(vib or 0)

            if prev_ts is not None:
                gap_sec = (ts - prev_ts).total_seconds()

                # Skip gaps > SENSOR_TIMEOUT_SEC (sensor was offline)
                if gap_sec > SENSOR_TIMEOUT_SEC:
                    log.debug(f'📊  gap {gap_sec:.0f}s > {SENSOR_TIMEOUT_SEC}s → skipped (sensor offline)')
                    skipped_gaps += 1
                    if in_cycle:
                        # close open cycle
                        burst = (prev_ts - cycle_start).total_seconds() if cycle_start else 0
                        if burst >= MIN_CYCLE_SECS:
                            cycles += 1
                            log.debug(f'📊  cycle closed on gap  →  burst={burst:.0f}s  total_cycles={cycles}')
                        in_cycle = False
                    prev_ts = ts
                    continue

                if vib_val > VIB_THRESHOLD:
                    operating_sec += gap_sec
                    above_thresh  += 1
                    if not in_cycle:
                        in_cycle    = True
                        cycle_start = prev_ts
                else:
                    idle_sec     += gap_sec
                    below_thresh += 1
                    if in_cycle:
                        burst = (ts - cycle_start).total_seconds() if cycle_start else 0
                        if burst >= MIN_CYCLE_SECS:
                            cycles += 1
                            log.debug(f'📊  cycle complete  →  burst={burst:.0f}s  total_cycles={cycles}')
                        in_cycle = False

            prev_ts = ts

        # Close any still-open cycle at end of data
        if in_cycle and cycle_start and prev_ts:
            burst = (prev_ts - cycle_start).total_seconds()
            if burst >= MIN_CYCLE_SECS:
                cycles += 1
                log.debug(f'📊  last cycle closed  →  burst={burst:.0f}s  total_cycles={cycles}')

        log.info(f'📊  vibration analysis  →  '
                 f'above_threshold={above_thresh}  '
                 f'below_threshold={below_thresh}  '
                 f'skipped_gaps={skipped_gaps}')

        if above_thresh == 0:
            log.warning(f'📊  ALL vibration readings are ≤ {VIB_THRESHOLD} mm/s  →  '
                        f'operating_time will be 0  |  try lowering VIB_THRESHOLD')

        # ── Energy from voltage data ─────────────────────────────
        cur.execute("""
            SELECT sensor_id, power, timestamp
            FROM   voltage_data
            WHERE  timestamp >= %s
            ORDER  BY sensor_id, timestamp ASC
        """, (today_start,))
        volt_rows = cur.fetchall()

        log.info(f'📊  voltage rows today  →  {len(volt_rows)} records')

        if not volt_rows:
            log.warning('📊  NO voltage records found for today  →  energy_used will be 0')

        energy_wh = 0.0
        sprev     = {}

        for sid, pwr, ts in volt_rows:
            if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            pwr = float(pwr or 0)
            if sid in sprev:
                prev_p, prev_t = sprev[sid]
                gap = (ts - prev_t).total_seconds()
                if gap <= SENSOR_TIMEOUT_SEC:
                    energy_wh += ((pwr + prev_p) / 2) * (gap / 3600)
            sprev[sid] = (pwr, ts)

        cur.close()

        result = {
            'operating_time': round(operating_sec / 3600, 2),
            'idle_time':      round(idle_sec      / 3600, 2),
            'cycles_today':   cycles,
            'energy_used':    round(energy_wh / 1000, 3)
        }

        log.info(f'📊  KPI result  →  '
                 f'operating={result["operating_time"]}hrs  '
                 f'idle={result["idle_time"]}hrs  '
                 f'cycles={result["cycles_today"]}  '
                 f'energy={result["energy_used"]}kWh')

        return result

    except Exception as e:
        log.exception(f'📊  calculate_kpi_today ERROR  →  {e}')
        return None
    finally:
        conn.close()
        log.debug('📊  DB connection closed')