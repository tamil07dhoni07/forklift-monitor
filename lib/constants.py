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

CLOUD_API_BASE   = 'https://your-cloud-api.com/api/v1'
CLOUD_API_KEY    = 'your-api-key-here'
CAM_STREAM_URL   = 'http://127.0.0.1:8080/?action=stream'
