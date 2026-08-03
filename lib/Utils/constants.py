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


DB_CONFIG = {
    'host':     'localhost',
    'port':     5432,
    'dbname':   'vibration_db',
    'user':     'postgres',
    'password': 'root'
}

CAM_STREAM_URL   = 'http://127.0.0.1:8080/?action=stream'

# ── CONFIG ───────────────────────────────────────────────────────
CLOUD_API_URL     = 'https://dev-edgedata.onelign.com'
CLOUD_API_KEY     = 'geariq-edge-secret-2024'
SYNC_INTERVAL_SEC = 60
BATCH_SIZE        = 20
RETRY_MAX         = 3
RETRY_DELAY_SEC   = 5

LOGIN_USERNAME = "admin.edgedata@onelign.com"
LOGIN_PASSWORD = "onelign@2025"

AUTH_URL = f"{CLOUD_API_URL}/api/auth/login"

DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'gearid_db', 'user': 'postgres', 'password': 'root'
}
# ─────────────────────────────────────────────────────────────────



# ── Thresholds ───────────────────────────────────────────────────
THRESHOLDS = {
    'voltage_high':       12.8,    # V  — overvoltage per cell
    'voltage_low':        11.5,    # V  — undervoltage per cell
    'battery_soc_low':    20,      # %  — low state of charge
    'battery_overcurrent':100,     # A  — total battery overcurrent
    'motor_temp_high':    80,      # °C — motor over temperature
    'motor_overcurrent':  150,     # A  — armature overcurrent spike
    'vibration_anomaly':  3.5,     # mm/s — abnormal vibration
    'zero_current_vib':   0.3,     # mm/s — vib threshold for open circuit check
}

# ── Fault Code Definitions ───────────────────────────────────────
FAULT_CATALOG = {
    # ── Direct Detection ─────────────────────────────────────────
    '1600': {
        'type':        'DIRECT',
        'severity':    'CRITICAL',
        'oem_desc':    'Battery voltage too high',
        'gear_iq':     'Cell voltage monitor (PZEM-017) — overvoltage detection',
        'sensor':      'battery',
    },
    '2C00': {
        'type':        'DIRECT',
        'severity':    'CRITICAL',
        'oem_desc':    'Battery voltage too low',
        'gear_iq':     'Cell voltage monitor (PZEM-017) — undervoltage / low SOC',
        'sensor':      'battery',
    },
    'FFF6': {
        'type':        'DIRECT',
        'severity':    'CRITICAL',
        'oem_desc':    'Battery over-current fault',
        'gear_iq':     'Battery current sensor — overcurrent event detection',
        'sensor':      'battery',
    },
    'FF31': {
        'type':        'DIRECT',
        'severity':    'CRITICAL',
        'oem_desc':    'Motor over temperature trip',
        'gear_iq':     'Motor temperature sensor (PT100) — thermal threshold breach',
        'sensor':      'motor',
    },
    'FFFA': {
        'type':        'DIRECT',
        'severity':    'CRITICAL',
        'oem_desc':    'Armature overcurrent fault',
        'gear_iq':     'Motor current sensor (CT clamp) — current spike detection',
        'sensor':      'motor',
    },
    'FFF7': {
        'type':        'DIRECT',
        'severity':    'WARNING',
        'oem_desc':    'Field overcurrent',
        'gear_iq':     'Motor current sensor — field winding overcurrent pattern',
        'sensor':      'motor',
    },
    'FF10': {
        'type':        'DIRECT',
        'severity':    'CRITICAL',
        'oem_desc':    'Armature open circuit fault',
        'gear_iq':     'Motor current sensor — zero current reading during operation',
        'sensor':      'motor',
    },
    'FFF3': {
        'type':        'DIRECT',
        'severity':    'WARNING',
        'oem_desc':    'Possible armature wiring fault',
        'gear_iq':     'Motor current anomaly — erratic reading pattern',
        'sensor':      'motor',
    },

    # ── Cross-Sensor Inferred ────────────────────────────────────
    '4401': {
        'type':        'INFERRED',
        'severity':    'CRITICAL',
        'oem_desc':    'Possible controller fault',
        'gear_iq':     'Correlate vibration + current anomaly simultaneously',
        'sensor':      'motor+battery',
    },
    'FF0B': {
        'type':        'INFERRED',
        'severity':    'WARNING',
        'oem_desc':    'Controller in thermal foldback',
        'gear_iq':     'Motor temp rising + current reducing — thermal throttle signature',
        'sensor':      'motor+battery',
    },
    '2F01': {
        'type':        'INFERRED',
        'severity':    'WARNING',
        'oem_desc':    'Throttle displaced on start-up',
        'gear_iq':     'Motor current at startup — baseline check on power-on',
        'sensor':      'motor',
    },
}


