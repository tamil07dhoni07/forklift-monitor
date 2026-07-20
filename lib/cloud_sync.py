#!/usr/bin/env python3
# ================================================================
#  cloud_sync.py  —  Gear IQ Forklift Monitor
# ================================================================

import json
import logging
import time
import psycopg2
import requests
from datetime import datetime, timezone, timedelta
from db import get_db_connection
from config import DEVICE_ID, LOCATION  # ← add

# ── CONFIG ───────────────────────────────────────────────────────
CLOUD_API_URL     = 'https://192.168.0.3:8080/api/v1/ingest'
CLOUD_API_KEY     = 'geariq-edge-secret-2024'
SYNC_INTERVAL_SEC = 60
BATCH_SIZE        = 20
RETRY_MAX         = 3
RETRY_DELAY_SEC   = 5

DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'gearid_db', 'user': 'postgres', 'password': 'root'
}
# ─────────────────────────────────────────────────────────────────

IST = timezone(timedelta(hours=5, minutes=30))


# ════════════════════════════════════════════════════════════════
#  COLORED LOGGER
# ════════════════════════════════════════════════════════════════

class ColorFormatter(logging.Formatter):
    """Adds ANSI color to console output based on log level."""
    RESET  = '\033[0m'
    BOLD   = '\033[1m'
    COLORS = {
        logging.DEBUG:    '\033[36m',    # Cyan
        logging.INFO:     '\033[32m',    # Green
        logging.WARNING:  '\033[33m',    # Yellow
        logging.ERROR:    '\033[31m',    # Red
        logging.CRITICAL: '\033[35m',    # Magenta
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f'{color}{self.BOLD}{record.levelname:<8}{self.RESET}'
        return super().format(record)


def setup_logger():
    logger = logging.getLogger('cloud_sync')
    logger.setLevel(logging.DEBUG)

    # Console handler — colored
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(ColorFormatter(
        fmt='%(asctime)s  %(levelname)s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # File handler — plain text
    fh = logging.FileHandler('cloud_sync.log')
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


log = setup_logger()


# ════════════════════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════════════════════

def get_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        log.debug(f'🗄️  DB connected  →  {DB_CONFIG["dbname"]}@{DB_CONFIG["host"]}')
        return conn
    except Exception as e:
        log.error(f'🗄️  DB connection FAILED  →  {e}')
        return None


def enqueue(payload: dict) -> bool:
    """Insert one payload into cloud_sync_queue for later upload."""
    log.debug('📥  Enqueueing payload into cloud_sync_queue ...')
    conn = get_db()
    if not conn:
        log.error('📥  Enqueue FAILED — no DB connection')
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO cloud_sync_queue (payload, is_sync) VALUES (%s, 0)",
            [json.dumps(payload)]
        )
        conn.commit()
        cur.close()
        log.info(f'📥  Payload queued  →  device={payload.get("device_id")}  '
                 f'motor={len(payload.get("sensors",{}).get("motor",[]))} rows  '
                 f'battery={len(payload.get("sensors",{}).get("battery",[]))} rows')
        return True
    except Exception as e:
        log.error(f'📥  Enqueue FAILED  →  {e}')
        conn.rollback()
        return False
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
#  BUILD PAYLOAD
# ════════════════════════════════════════════════════════════════

def build_payload(vib_rows, volt_rows, oil_rows, kpi) -> dict:
    """Build the JSON body matching the cloud API contract."""
    now_ist = datetime.now(IST).isoformat()

    log.debug(f'🔧  Building payload  →  '
              f'vib={len(vib_rows or [])}  '
              f'volt={len(volt_rows or [])}  '
              f'oil={len(oil_rows or [])}  '
              f'kpi={bool(kpi)}')

    motor_list = []
    for r in (vib_rows or []):
        motor_list.append({
            'id':              r.get('id'),
            'total_vibration': float(r.get('total_vibration', 0)),
            'temperature':     float(r.get('temperature', 0)),
            'velocity': {
                'x': float(r.get('velocity_x', r.get('velocity', {}).get('x', 0))),
                'y': float(r.get('velocity_y', r.get('velocity', {}).get('y', 0))),
                'z': float(r.get('velocity_z', r.get('velocity', {}).get('z', 0))),
            },
            'status':      r.get('status', 'ok'),
            'recorded_at': str(r.get('recorded_at', now_ist)),
        })

    battery_list = []
    for r in (volt_rows or []):
        battery_list.append({
            'id':          r.get('id'),
            'sensor_id':   r.get('sensor_id'),
            'voltage':     float(r.get('voltage', 0)),
            'current':     float(r.get('current', 0)),
            'power':       float(r.get('power', 0)),
            'energy':      float(r.get('energy', 0)),
            'status':      r.get('status', 'ok'),
            'recorded_at': str(r.get('recorded_at', now_ist)),
        })

    oil_list = []
    for r in (oil_rows or []):
        oil_list.append({
            'id':          r.get('id'),
            'level':       float(r.get('level', 0)),
            'temperature': float(r.get('temperature', 0)),
            'oil_quality': float(r.get('oil_quality', 0)),
            'pressure':    float(r.get('pressure', 0)),
            'status':      r.get('status', 'ok'),
            'recorded_at': str(r.get('recorded_at', now_ist)),
        })

    payload = {
        'device_id': DEVICE_ID,
        'synced_at': now_ist,
        'sensors': {
            'motor':   motor_list,
            'battery': battery_list,
            'oil':     oil_list,
            'kpi': {
                'operating_time': float((kpi or {}).get('operating_time', 0)),
                'idle_time':      float((kpi or {}).get('idle_time', 0)),
                'cycles_today':   int  ((kpi or {}).get('cycles_today', 0)),
                'energy_used':    float((kpi or {}).get('energy_used', 0)),
            }
        }
    }

    log.debug(f'🔧  Payload built  →  synced_at={now_ist}')
    return payload


# ════════════════════════════════════════════════════════════════
#  POST TO CLOUD
# ════════════════════════════════════════════════════════════════

def post_to_cloud(payload: dict) -> bool:
    """POST payload to cloud. Returns True only on HTTP 200/201/202."""
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key':    CLOUD_API_KEY,
        'X-Device-Id':  DEVICE_ID,
    }

    log.info(f'☁️   Posting to cloud  →  {CLOUD_API_URL}')

    for attempt in range(1, RETRY_MAX + 1):
        try:
            log.debug(f'☁️   Attempt {attempt}/{RETRY_MAX}  →  sending request ...')
            log.debug(f'☁️   payload {payload}  ')

            resp = requests.post(
                CLOUD_API_URL,
                json=payload,
                headers=headers,
                timeout=15
            )

            if resp.status_code in (200, 201, 202):
                log.info(f'☁️   POST success  →  HTTP {resp.status_code}  '
                         f'device={payload.get("device_id")}  '
                         f'synced_at={payload.get("synced_at","?")}')
                return True

            log.warning(f'☁️   Attempt {attempt}/{RETRY_MAX} FAILED  →  '
                        f'HTTP {resp.status_code}  body={resp.text[:120]}')

        except requests.exceptions.ConnectionError:
            log.warning(f'☁️   Attempt {attempt}/{RETRY_MAX}  →  '
                        f'Cannot reach cloud ({CLOUD_API_URL})')
        except requests.exceptions.Timeout:
            log.warning(f'☁️   Attempt {attempt}/{RETRY_MAX}  →  Request timed out (15s)')
        except Exception as e:
            log.error(f'☁️   Attempt {attempt}/{RETRY_MAX}  →  Unexpected error: {e}')

        if attempt < RETRY_MAX:
            log.debug(f'☁️   Waiting {RETRY_DELAY_SEC}s before retry ...')
            time.sleep(RETRY_DELAY_SEC)

    log.error(f'☁️   All {RETRY_MAX} attempts exhausted  →  row kept for next cycle')
    return False


# ════════════════════════════════════════════════════════════════
#  SYNC CYCLE  —  Read → POST → DELETE
# ════════════════════════════════════════════════════════════════

def sync_cycle():
    log.debug('─' * 55)
    log.debug('🔄  Starting sync cycle ...')

    conn = get_db()
    if not conn:
        log.error('🔄  Sync cycle ABORTED  →  no DB connection')
        return

    cur = conn.cursor()
    try:
        # Fetch pending rows oldest first
        cur.execute("""
            SELECT id, payload, created_at
            FROM   cloud_sync_queue
            WHERE  is_sync = 0
            ORDER  BY created_at ASC
            LIMIT  %s
        """, (BATCH_SIZE,))
        rows = cur.fetchall()

        if not rows:
            log.info('🔄  Queue empty  →  nothing to sync')
            return

        log.info(f'🔄  Found {len(rows)} pending row(s) in queue')

        sent = skipped = 0

        for row_id, payload, created_at in rows:
            log.debug(f'📤  Processing row id={row_id}  created={created_at}')

            # psycopg2 auto-parses JSONB → dict; handle string just in case
            if isinstance(payload, str):
                payload = json.loads(payload)

            if post_to_cloud(payload):
                cur.execute(
                    "DELETE FROM cloud_sync_queue WHERE id = %s",
                    (row_id,)
                )
                conn.commit()
                log.info(f'🗑️   Row id={row_id} DELETED  →  POST successful')
                sent += 1
            else:
                log.warning(f'⏳  Row id={row_id} KEPT  →  will retry next cycle')
                skipped += 1

        log.info(f'🔄  Cycle complete  →  ✅ sent={sent}  ⏳ pending={skipped}  '
                 f'total={len(rows)}')

    except Exception as e:
        conn.rollback()
        log.exception(f'🔄  Sync cycle ERROR  →  {e}')
    finally:
        cur.close()
        conn.close()
        log.debug('🗄️  DB connection closed')


# ════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════

def main():
    log.info('=' * 55)
    log.info('🚀  Gear IQ Cloud Sync Daemon  STARTED')
    log.info(f'    Device ID   : {DEVICE_ID}')
    log.info(f'    Location    : {LOCATION}')
    log.info(f'    Cloud URL   : {CLOUD_API_URL}')
    log.info(f'    DB          : {DB_CONFIG["dbname"]}@{DB_CONFIG["host"]}:{DB_CONFIG["port"]}')
    log.info(f'    Interval    : every {SYNC_INTERVAL_SEC}s')
    log.info(f'    Batch size  : {BATCH_SIZE} rows')
    log.info(f'    Retries     : {RETRY_MAX}× per row')
    log.info('=' * 55)

    cycle_count = 0
    while True:
        try:
            cycle_count += 1
            log.debug(f'⏱️   Cycle #{cycle_count}  →  '
                      f'{datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")}')
            sync_cycle()
        except Exception as e:
            log.exception(f'💥  Unhandled error in daemon loop  →  {e}')

        log.debug(f'😴  Sleeping {SYNC_INTERVAL_SEC}s until next cycle ...')
        time.sleep(SYNC_INTERVAL_SEC)


if __name__ == '__main__':
    main()