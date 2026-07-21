# ================================================================
#  constants.py  —  Gear IQ Forklift Monitor
#  Single source of truth for the current software version.
#
#  To release a new version:
#    1. Update VERSION here
#    2. Push to GitHub
#    3. Cloud dashboard sets the required version to match
# ================================================================

VERSION = 1          # current installed version (integer)

DEVICE_ID = 'FL-2024'
LOCATION  = 'Warehouse A — Bay 3'

DB_CONFIG = {
    'host':     'localhost',
    'port':     5432,
    'dbname':   'vibration_db',
    'user':     'postgres',
    'password': 'root'
}

CAM_STREAM_URL   = 'http://127.0.0.1:8080/?action=stream'

# ── CONFIG ───────────────────────────────────────────────────────
CLOUD_API_URL     = 'https://192.168.0.3:8080/api/geariq/v1/ingest'
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

