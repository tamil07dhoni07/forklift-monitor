#!/usr/bin/env python3
# ================================================================
#  cloud_sync.py  —  Gear IQ Forklift Monitor
#
#  Queue-based cloud uploader:
#   1. Reads rows from cloud_sync_queue WHERE is_sync = 0
#   2. POSTs each payload to the cloud API
#   3. On HTTP 200/201/202  → DELETE the row (gone forever)
#   4. On failure           → keep row, retry next cycle
#
#  To add a payload to the queue call:  enqueue(payload_dict)
#  To run as daemon:  python3 cloud_sync.py
# ================================================================

import json
import logging
import time
import psycopg2
import requests
from datetime import datetime, timezone, timedelta

# ── ① CONFIG — change these ──────────────────────────────────────
CLOUD_API_URL = 'https://your-cloud-api.com/api/v1/ingest'  # ← set
CLOUD_API_KEY = 'your-api-key-here'                          # ← set
DEVICE_ID     = 'FL-2024'
LOCATION      = 'Warehouse A — Bay 3'

SYNC_INTERVAL_SEC = 60     # how often to check the queue
BATCH_SIZE        = 20     # max rows to process per cycle
RETRY_MAX         = 3      # HTTP attempts before giving up this row
RETRY_DELAY_SEC   = 5      # wait between retries

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'gearid_db',
    'user': 'postgres',
    'password': 'root'
}
# ────────────────────────────────────────────────────────────────

IST = timezone(timedelta(hours=5, minutes=30))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('cloud_sync.log'), logging.StreamHandler()]
)
log = logging.getLogger('cloud_sync')


# ════════════════════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════════════════════

def get_db():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        log.error(f'DB connection failed: {e}')
        return None


def enqueue(payload: dict) -> bool:
    """
    Insert one payload snapshot into cloud_sync_queue.
    Call this from api_server.py every time sensor data is collected.

    Example:
        payload = build_payload(vib_data, voltage_data, kpi_data)
        enqueue(payload)
    """
    conn = get_db()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO cloud_sync_queue (payload, is_sync) VALUES (%s, 0)",
            [json.dumps(payload)]
        )
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        log.error(f'enqueue failed: {e}')
        conn.rollback()
        return False
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
#  BUILD PAYLOAD  (matches Postman format exactly)
# ════════════════════════════════════════════════════════════════

def build_payload(vib_rows, volt_rows, oil_rows, kpi) -> dict:
    """
    Build the JSON body that matches your cloud API contract:
    {
      "device_id": "FL-2024",
      "synced_at": "<IST ISO timestamp>",
      "sensors": {
        "motor":   [ { id, total_vibration, temperature,
                       velocity:{x,y,z}, status, recorded_at } ],
        "battery": [ { id, sensor_id, voltage, current,
                       power, energy, status, recorded_at } ],
        "oil":     [ { id, level, temperature, oil_quality,
                       pressure, status, recorded_at } ],
        "kpi":     { operating_time, idle_time,
                     cycles_today, energy_used }
      }
    }
    """
    now_ist = datetime.now(IST).isoformat()

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

    return {
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


# ════════════════════════════════════════════════════════════════
#  POST TO CLOUD
# ════════════════════════════════════════════════════════════════

def post_to_cloud(payload: dict) -> bool:
    """POST payload. Returns True only on HTTP 200/201/202."""
    headers = {
        'Content-Type':  'application/json',
        'Authorization': f'Bearer {CLOUD_API_KEY}',
        'X-Device-Id':   DEVICE_ID,
    }
    for attempt in range(1, RETRY_MAX + 1):
        try:
            resp = requests.post(
                CLOUD_API_URL,
                json=payload,
                headers=headers,
                timeout=15
            )
            if resp.status_code in (200, 201, 202):
                log.info(f'✅ Cloud accepted payload (HTTP {resp.status_code})')
                return True
            log.warning(f'Attempt {attempt}/{RETRY_MAX}: HTTP {resp.status_code} — {resp.text[:120]}')
        except requests.exceptions.ConnectionError:
            log.warning(f'Attempt {attempt}/{RETRY_MAX}: Cannot reach cloud')
        except requests.exceptions.Timeout:
            log.warning(f'Attempt {attempt}/{RETRY_MAX}: Request timed out')
        except Exception as e:
            log.error(f'Attempt {attempt}/{RETRY_MAX}: {e}')

        if attempt < RETRY_MAX:
            time.sleep(RETRY_DELAY_SEC)

    log.error('❌ All retry attempts exhausted — row kept for next cycle')
    return False


# ════════════════════════════════════════════════════════════════
#  MAIN SYNC CYCLE
#  Read → POST → DELETE  (or keep on failure)
# ════════════════════════════════════════════════════════════════

def sync_cycle():
    conn = get_db()
    if not conn:
        log.error('Skipping cycle — no DB connection')
        return

    cur = conn.cursor()
    try:
        # Fetch pending rows oldest first
        cur.execute("""
            SELECT id, payload
            FROM   cloud_sync_queue
            WHERE  is_sync = 0
            ORDER  BY created_at ASC
            LIMIT  %s
        """, (BATCH_SIZE,))
        rows = cur.fetchall()

        if not rows:
            log.info('Queue empty — nothing to sync')
            return

        log.info(f'Found {len(rows)} pending row(s) to sync')

        sent = 0
        for row_id, payload in rows:
            # payload comes back as dict (psycopg2 auto-parses JSONB)
            if isinstance(payload, str):
                payload = json.loads(payload)

            if post_to_cloud(payload):
                # ✅ Success → DELETE the row permanently
                cur.execute(
                    "DELETE FROM cloud_sync_queue WHERE id = %s",
                    (row_id,)
                )
                conn.commit()
                log.info(f'  🗑  Deleted queue row id={row_id}')
                sent += 1
            else:
                # ❌ Failure → leave row, will retry next cycle
                log.warning(f'  ⏳ Row id={row_id} kept for retry')

        log.info(f'Cycle done — sent {sent}/{len(rows)} payloads')

    except Exception as e:
        conn.rollback()
        log.exception(f'Sync cycle error: {e}')
    finally:
        cur.close()
        conn.close()


# ════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════

def main():
    log.info(f'🚀 Cloud Sync Daemon started  →  {CLOUD_API_URL}')
    log.info(f'   Polling every {SYNC_INTERVAL_SEC}s  |  batch={BATCH_SIZE}  |  retries={RETRY_MAX}')
    while True:
        try:
            sync_cycle()
        except Exception as e:
            log.exception(f'Unhandled error in daemon: {e}')
        time.sleep(SYNC_INTERVAL_SEC)


if __name__ == '__main__':
    main()


# ════════════════════════════════════════════════════════════════
#  HOW TO WIRE INTO api_server.py
# ════════════════════════════════════════════════════════════════
#
#  At the bottom of your sensor-data write function, call enqueue():
#
#  from cloud_sync import build_payload, enqueue
#
#  # After saving sensor rows to PostgreSQL:
#  payload = build_payload(
#      vib_rows  = [vib_record],    # list of vibration dicts
#      volt_rows = voltage_records,  # list of voltage dicts
#      oil_rows  = oil_records,      # list of oil dicts (or [])
#      kpi       = kpi_dict          # {operating_time, idle_time, ...}
#  )
#  enqueue(payload)   # saves to cloud_sync_queue; daemon will POST + delete
#
# ════════════════════════════════════════════════════════════════
#  SYSTEMD UNIT  (/etc/systemd/system/geariq-cloud-sync.service)
# ════════════════════════════════════════════════════════════════
#
#  [Unit]
#  Description=Gear IQ Cloud Sync
#  After=network.target postgresql.service
#
#  [Service]
#  ExecStart=/usr/bin/python3 /opt/geariq/cloud_sync.py
#  WorkingDirectory=/opt/geariq
#  Restart=always
#  RestartSec=10
#  User=linaro
#
#  [Install]
#  WantedBy=multi-user.target
#
#  Enable:
#    sudo systemctl daemon-reload
#    sudo systemctl enable geariq-cloud-sync
#    sudo systemctl start  geariq-cloud-sync
#    sudo systemctl status geariq-cloud-sync
