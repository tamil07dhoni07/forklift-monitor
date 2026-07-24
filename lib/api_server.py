#!/usr/bin/env python3
# ============================================
# FORKLIFT MONITOR - API SERVER (Multi-voltage)
# ============================================
from cloud_sync import build_payload, enqueue
from kpi_logic  import calculate_kpi_today
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from db import delete_old_vibration_records, delete_old_voltage_records, get_db_connection
from datetime import datetime, timedelta
from config import DEVICE_ID, HOSTNAME, LOCATION
from constants import VERSION
from fault_codes import detect_faults, fault_summary
import logging
from device_register import register_device

app = Flask(__name__,
            static_folder='../web/static',
            static_url_path='/static',
            template_folder='../web/templates')
CORS(app)

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'gearid_db',
    'user': 'postgres',
    'password': 'root'
}

MAX_OIL_VOLUME_L = 10.0   # ← set your tank max capacity in litres



# ════════════════════════════════════════════════════════════════
#  COLORED LOGGER
# ════════════════════════════════════════════════════════════════

class ColorFormatter(logging.Formatter):
    RESET  = '\033[0m'
    BOLD   = '\033[1m'
    COLORS = {
        logging.DEBUG:    '\033[36m',
        logging.INFO:     '\033[32m',
        logging.WARNING:  '\033[33m',
        logging.ERROR:    '\033[31m',
        logging.CRITICAL: '\033[35m',
    }
    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f'{color}{self.BOLD}{record.levelname:<8}{self.RESET}'
        return super().format(record)

def setup_logger():
    logger = logging.getLogger('api_server')
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(ColorFormatter(
        fmt='%(asctime)s  %(levelname)s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    fh = logging.FileHandler('api_server.log')
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
#  DB HELPERS
# ════════════════════════════════════════════════════════════════

def get_latest_vibration():
    log.debug('🔍  get_latest_vibration  →  querying DB ...')
    conn = get_db_connection()
    if not conn:
        log.error('🔍  get_latest_vibration  →  no DB connection')
        return None
    cur = conn.cursor()
    cur.execute("""
        SELECT total_vibration, temperature, velocity_x, velocity_y, velocity_z, timestamp
        FROM vibration_sensor_data ORDER BY id DESC LIMIT 1
    """)
    row = cur.fetchone()
    cur.close(); conn.close()
    if row:
        log.debug(f'🔍  vibration fetched  →  vib={row[0]}  temp={row[1]}°C  ts={row[5]}')
        return {
            'total_vibration': row[0],
            'temperature': row[1],
            'velocity': {'x': row[2], 'y': row[3], 'z': row[4]},
            'timestamp': row[5]
        }
    log.warning('🔍  get_latest_vibration  →  no rows found')
    return None


def get_latest_voltages():
    log.debug('🔍  get_latest_voltages  →  querying DB ...')
    conn = get_db_connection()
    if not conn:
        log.error('🔍  get_latest_voltages  →  no DB connection')
        return []
    cur = conn.cursor()
    # cur.execute("""
    #     SELECT DISTINCT ON (sensor_id) sensor_id, voltage, current, power, energy, timestamp
    #     FROM voltage_data ORDER BY sensor_id, id DESC
    # """)
    cur.execute("""
        WITH latest_voltage AS (
        SELECT DISTINCT ON (sensor_id)
           sensor_id,
           voltage,
           current,
           power,
           energy,
           timestamp
            FROM voltage_data
            ORDER BY sensor_id, id DESC
            ),
            latest_temperature AS (
            SELECT DISTINCT ON (sensor_id)
           sensor_id,
           temperature,
           status,
           timestamp AS temp_timestamp
            FROM temperature_data
            ORDER BY sensor_id, id DESC
            )
            SELECT
            v.sensor_id,
            v.voltage,
            v.current,
            v.power,
            v.energy,
            v.timestamp,
            t.temperature,
            t.status,
            t.temp_timestamp
            FROM latest_voltage v
            LEFT JOIN latest_temperature t
            ON v.sensor_id =
            CASE t.sensor_id
            WHEN 1 THEN 2
            WHEN 2 THEN 3
            WHEN 3 THEN 4
            WHEN 4 THEN 6
            END
            ORDER BY v.sensor_id;
            """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    log.debug(f'🔍  voltages fetched  →  {len(rows)} sensor(s)')
    for r in rows:
        log.debug(f'    sensor_id={r[0]}  voltage={r[1]:.2f}V  current={r[2]:.2f}A  power={r[3]:.1f}W  temperature={r[6]}°C  status={r[7]}  ts={r[5]}  temp_ts={r[8]}')
    return [{
        'sensor_id': r[0], 'voltage': r[1], 'current': r[2],
        'power': r[3],     'energy':  r[4], 'timestamp': r[5], 'temperature': r[6], 'status': r[7], 'temp_timestamp': r[8]
    } for r in rows]


def get_latest_temperatures():
    log.debug('🌡️   get_latest_temperatures  →  querying DB ...')
    conn = get_db_connection()
    if not conn:
        log.error('🌡️   get_latest_temperatures  →  no DB connection')
        return []
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (sensor_id)
                   sensor_id, temperature, status, timestamp
            FROM   temperature_data
            ORDER  BY sensor_id, id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        log.debug(f'🌡️   temperatures fetched  →  {len(rows)} sensor(s)')
        for r in rows:
            log.debug(f'    sensor_id={r[0]}  temp={r[1]}°C  status={r[2]}')
        return [{
            'sensor_id':   r[0],
            'temperature': r[1],
            'status':      r[2],
            'timestamp':   r[3]
        } for r in rows]
    except Exception as e:
        log.error(f'🌡️   get_latest_temperatures ERROR  →  {e}')
        return []
    finally:
        conn.close()

# ── Hydraulic oil config ──────────────────────────────────────────

def get_latest_hydraulic():
    log.debug('🛢️   get_latest_hydraulic  →  querying DB ...')
    conn = get_db_connection()
    if not conn:
        log.error('🛢️   get_latest_hydraulic  →  no DB connection')
        return None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT temperature, raw_distance_mm, fuel_level_cm,
                   oil_height_mm, volume_ml, rounded_volume_l,
                   status, timestamp
            FROM   fuel_level_sensor_data
            ORDER  BY id DESC LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        if not row:
            log.warning('🛢️   get_latest_hydraulic  →  no rows found')
            return None

        volume_l  = float(row[5] or 0)
        level_pct = round(min(100, (volume_l / MAX_OIL_VOLUME_L) * 100), 1)

        log.debug(f'🛢️   hydraulic fetched  →  '
                  f'temp={row[0]}°C  '
                  f'volume={volume_l}L  '
                  f'level={level_pct}%  '
                  f'status={row[6]}  '
                  f'ts={row[7]}')

        return {
            'temperature':     float(row[0] or 0),
            'raw_distance_mm': float(row[1] or 0),
            'fuel_level_cm':   float(row[2] or 0),
            'oil_height_mm':   float(row[3] or 0),
            'volume_ml':       float(row[4] or 0),
            'volume_l':        volume_l,
            'level_pct':       level_pct,
            'status':          row[6],
            'timestamp':       row[7].isoformat()
        }
    except Exception as e:
        log.error(f'🛢️   get_latest_hydraulic ERROR  →  {e}')
        return None
    finally:
        conn.close()



# ════════════════════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    log.info('🌐  GET /  →  serving index.html')
    return send_from_directory(app.template_folder, 'index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    log.debug(f'🌐  GET /static/{filename}')
    return send_from_directory(app.static_folder, filename)


@app.route('/api/health')
def health():
    log.debug('💓  GET /api/health  →  running')
    return jsonify({'status': 'running', 'timestamp': datetime.now().isoformat()})


@app.route('/api/vibration')
def vibration():
    log.info('─' * 45)
    log.info('📡  GET /api/vibration  →  processing ...')

    rec  = get_latest_vibration()
    volt = get_latest_voltages()
    data = calculate_kpi_today()
    oilData = get_latest_hydraulic()
    log.debug(f'📊  KPI  →  {data}')

    if rec and (datetime.now() - rec['timestamp']) < timedelta(seconds=10):
        age = (datetime.now() - rec['timestamp']).total_seconds()
        log.info(f'📡  sensor ONLINE  →  '
                 f'vib={rec["total_vibration"]:.2f} mm/s  '
                 f'temp={rec["temperature"]:.1f}°C  '
                 f'vel=({rec["velocity"]["x"]:.2f},{rec["velocity"]["y"]:.2f},{rec["velocity"]["z"]:.2f})  '
                 f'age={age:.1f}s')

        response = {
            'status':          'online',
            'total_vibration': rec['total_vibration'],
            'temperature':     rec['temperature'],
            'velocity':        rec['velocity'],
            'timestamp':       rec['timestamp'].isoformat()
        }

        try:
            log.debug('☁️   building cloud payload ...')
            payload = build_payload(
                vib_rows  = [rec],
                volt_rows = volt,
                oil_rows  = oilData,
                kpi       = data
            )
            enqueue(payload)
            log.info('☁️   payload queued  →  ✅')
        except Exception as e:
            log.error(f'☁️   enqueue FAILED  →  {e}')

        return jsonify(response)

    else:
        if not rec:
            log.warning('📡  sensor OFFLINE  →  no records in DB')
        else:
            age = (datetime.now() - rec['timestamp']).total_seconds()
            log.warning(f'📡  sensor OFFLINE  →  last record {age:.1f}s old (threshold=10s)')
        return jsonify({
            'status': 'offline',
            'total_vibration': 0,
            'temperature': 0,
            'velocity': {'x': 0, 'y': 0, 'z': 0}
        })


@app.route('/api/voltages')
def voltages():
    log.info('🔋  GET /api/voltages  →  processing ...')
    recs = get_latest_voltages()
    now  = datetime.now()
    result = []
    for r in recs:
        age      = (now - r['timestamp']).total_seconds()
        r['status'] = 'online' if age < 10 else 'offline'
        log.debug(f'🔋  sensor_id={r["sensor_id"]}  voltage={r["voltage"]:.2f}V  '
                  f'status={r["status"]}  age={age:.1f}s')
        result.append(r)
    online = sum(1 for r in result if r['status'] == 'online')
    log.info(f'🔋  response  →  {len(result)} sensor(s)  online={online}  offline={len(result)-online}')
    return jsonify(result)


@app.route('/api/voltage/<int:sensor_id>')
def voltage_sensor(sensor_id):
    log.info(f'🔋  GET /api/voltage/{sensor_id}  →  processing ...')
    recs = get_latest_voltages()
    for r in recs:
        if r['sensor_id'] == sensor_id:
            age    = (datetime.now() - r['timestamp']).total_seconds()
            online = age < 10
            status = 'online' if online else 'offline'
            log.info(f'🔋  sensor_id={sensor_id}  voltage={r["voltage"]:.2f}V  '
                     f'status={status}  age={age:.1f}s')
            return jsonify({**r, 'status': status})
    log.warning(f'🔋  sensor_id={sensor_id}  →  NOT FOUND in DB')
    return jsonify({'status': 'offline', 'voltage': 0, 'current': 0, 'power': 0, 'energy': 0})


@app.route('/api/kpi')
def kpi():
    log.info('📊  GET /api/kpi  →  calculating ...')
    data = calculate_kpi_today()
    if not data:
        log.warning('📊  KPI  →  no data returned  sending zeros')
        return jsonify({'operating_time': 0, 'idle_time': 0, 'cycles_today': 0, 'energy_used': 0})
    log.info(f'📊  KPI  →  op={data["operating_time"]}hrs  idle={data["idle_time"]}hrs  '
             f'cycles={data["cycles_today"]}  energy={data["energy_used"]}kWh')
    return jsonify(data)


@app.route('/api/device')
def device_info():
    log.info(f'📟  GET /api/device  →  device_id={DEVICE_ID}  location={LOCATION}  version={VERSION}')
    return jsonify({
        'device_id': DEVICE_ID,
        'location':  LOCATION,
        'hostname':  HOSTNAME,
        'version':   VERSION
    })


@app.route('/api/temperature')
def temperature():
    log.info('🌡️   GET /api/temperature  →  processing ...')
    recs   = get_latest_temperatures()
    now    = datetime.now()
    result = []
    for r in recs:
        age    = (now - r['timestamp']).total_seconds()
        status = 'online' if age < 10 else 'offline'
        log.debug(f'🌡️   sensor_id={r["sensor_id"]}  temp={r["temperature"]}°C  '
                  f'status={status}  age={age:.1f}s')
        result.append({**r, 'status': status, 'timestamp': r['timestamp'].isoformat()})
    online = sum(1 for r in result if r['status'] == 'online')
    log.info(f'🌡️   response  →  {len(result)} sensor(s)  online={online}')
    return jsonify(result)


@app.route('/api/faults')
def faults():
    log.info('⚠️   GET /api/faults  →  running detection ...')

    vib_data  = get_latest_vibration()
    volt_data = get_latest_voltages()

    active_faults = detect_faults(
        vib_data  = vib_data,
        volt_data = volt_data,
    )

    summary = fault_summary(active_faults)

    log.info(f'⚠️   faults  →  total={summary["total"]}  '
             f'critical={summary["critical"]}  '
             f'warning={summary["warning"]}  '
             f'status={summary["status"]}')

    if active_faults:
        for f in active_faults:
            log.warning(f'    [{f["severity"]}] {f["code"]}  {f["oem_desc"]}  →  {f["value"]}')
    else:
        log.info('⚠️   no active faults  →  all systems normal')

    return jsonify(summary)


@app.route('/api/hydraulic')
def hydraulic():
    log.info('🛢️   GET /api/hydraulic  →  processing ...')
    rec = get_latest_hydraulic()
    if not rec:
        log.warning('🛢️   hydraulic  →  no data')
        return jsonify({'status': 'offline', 'level_pct': 0,
                        'temperature': 0, 'volume_l': 0})

    age    = (datetime.now() - datetime.fromisoformat(rec['timestamp'])).total_seconds()
    online = age < 10
    rec['status'] = 'online' if online else 'offline'

    log.info(f'🛢️   response  →  '
             f'level={rec["level_pct"]}%  '
             f'temp={rec["temperature"]}°C  '
             f'volume={rec["volume_l"]}L  '
             f'status={rec["status"]}  '
             f'age={age:.1f}s')
    return jsonify(rec)


# ════════════════════════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    log.info('=' * 55)
    log.info('🚀  Gear IQ API Server  STARTING')
    log.info(f'    Device ID  : {DEVICE_ID}')
    log.info(f'    Location   : {LOCATION}')
    log.info(f'    Hostname   : {HOSTNAME}')
    log.info(f'    Version    : {VERSION}')
    log.info(f'    DB         : {DB_CONFIG["dbname"]}@{DB_CONFIG["host"]}:{DB_CONFIG["port"]}')
    log.info(f'    Host       : 0.0.0.0:5000')
    log.info('=' * 55)

    log.info('[Startup] Cleaning old records ...')
    delete_old_voltage_records()
    delete_old_vibration_records()
    log.info('[Startup] Cleanup done ✅')

    register_device()      

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)