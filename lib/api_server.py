#!/usr/bin/env python3
# ============================================
# FORKLIFT MONITOR - API SERVER (Multi-voltage)
# ============================================
from cloud_sync import build_payload, enqueue
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from datetime import datetime, timedelta

from kpi_logic import calculate_kpi_today

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

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"⚠️ DB connection error: {e}")
        return None

def get_latest_vibration():
    conn = get_db_connection()
    if not conn: return None
    cur = conn.cursor()
    cur.execute("""
        SELECT total_vibration, temperature, velocity_x, velocity_y, velocity_z, timestamp
        FROM vibration_sensor_data ORDER BY id DESC LIMIT 1
    """)
    row = cur.fetchone()
    cur.close(); conn.close()
    if row:
        return {
            'total_vibration': row[0],
            'temperature': row[1],
            'velocity': {'x': row[2], 'y': row[3], 'z': row[4]},
            'timestamp': row[5]
        }
    return None

def get_latest_voltages():
    conn = get_db_connection()
    if not conn: return []
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (sensor_id) sensor_id, voltage, current, power, energy, timestamp
        FROM voltage_data ORDER BY sensor_id, id DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{
        'sensor_id': r[0],
        'voltage': r[1],
        'current': r[2],
        'power': r[3],
        'energy': r[4],
        'timestamp': r[5]
    } for r in rows]

# ---------- Routes ----------
@app.route('/')
def index():
    return send_from_directory(app.template_folder, 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/api/health')
def health():
    return jsonify({'status': 'running', 'timestamp': datetime.now().isoformat()})

#!/usr/bin/env python3
# ================================================================
#  api_server.py  —  Gear IQ Forklift Monitor
# ================================================================

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from datetime import datetime, timedelta
import logging

from cloud_sync import build_payload, enqueue

app = Flask(__name__,
            static_folder='../web/static',
            static_url_path='/static',
            template_folder='../web/templates')
CORS(app)

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'vibration_db',
    'user': 'postgres',
    'password': 'root'
}


# ════════════════════════════════════════════════════════════════
#  COLORED LOGGER
# ════════════════════════════════════════════════════════════════

class ColorFormatter(logging.Formatter):
    RESET  = '\033[0m'
    BOLD   = '\033[1m'
    COLORS = {
        logging.DEBUG:    '\033[36m',   # Cyan
        logging.INFO:     '\033[32m',   # Green
        logging.WARNING:  '\033[33m',   # Yellow
        logging.ERROR:    '\033[31m',   # Red
        logging.CRITICAL: '\033[35m',   # Magenta
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
#  DATABASE HELPERS
# ════════════════════════════════════════════════════════════════

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        log.debug(f'🗄️  DB connected  →  {DB_CONFIG["dbname"]}@{DB_CONFIG["host"]}')
        return conn
    except Exception as e:
        log.error(f'🗄️  DB connection FAILED  →  {e}')
        return None


def get_latest_vibration():
    log.debug('🔍  Fetching latest vibration record ...')
    conn = get_db_connection()
    if not conn:
        log.error('🔍  get_latest_vibration FAILED  →  no DB connection')
        return None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT total_vibration, temperature,
                   velocity_x, velocity_y, velocity_z, timestamp
            FROM vibration_sensor_data
            ORDER BY id DESC LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        if row:
            log.debug(f'🔍  Vibration fetched  →  '
                      f'vib={row[0]:.2f} mm/s  temp={row[1]:.1f}°C  '
                      f'ts={row[5]}')
            return {
                'total_vibration': row[0],
                'temperature':     row[1],
                'velocity': {'x': row[2], 'y': row[3], 'z': row[4]},
                'timestamp': row[5]
            }
        log.warning('🔍  No vibration records found in DB')
        return None
    except Exception as e:
        log.error(f'🔍  get_latest_vibration ERROR  →  {e}')
        return None
    finally:
        conn.close()


def get_latest_voltages():
    log.debug('🔍  Fetching latest voltage records ...')
    conn = get_db_connection()
    if not conn:
        log.error('🔍  get_latest_voltages FAILED  →  no DB connection')
        return []
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (sensor_id)
                   sensor_id, voltage, current, power, energy, timestamp
            FROM voltage_data
            ORDER BY sensor_id, id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        log.debug(f'🔍  Voltages fetched  →  {len(rows)} sensor(s)')
        for r in rows:
            log.debug(f'    sensor_id={r[0]}  voltage={r[1]:.2f}V  '
                      f'current={r[2]:.2f}A  power={r[3]:.1f}W')
        return [{
            'sensor_id': r[0], 'voltage': r[1], 'current': r[2],
            'power': r[3],     'energy':  r[4], 'timestamp': r[5]
        } for r in rows]
    except Exception as e:
        log.error(f'🔍  get_latest_voltages ERROR  →  {e}')
        return []
    finally:
        conn.close()


def calculate_kpi_today():
    log.debug('📊  Calculating KPI for today ...')
    conn = get_db_connection()
    if not conn:
        log.error('📊  calculate_kpi_today FAILED  →  no DB connection')
        return None
    try:
        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time())
        cur = conn.cursor()

        # Operating time & cycles
        cur.execute("""
            SELECT total_vibration, timestamp
            FROM vibration_sensor_data
            WHERE timestamp >= %s
            ORDER BY timestamp ASC
        """, (today_start,))
        vib_rows = cur.fetchall()

        operating_sec = idle_sec = 0.0
        cycles = 0
        in_cycle = False
        cycle_start = prev_ts = None
        THRESH = 0.3

        for vib, ts in vib_rows:
            if prev_ts:
                gap = (ts - prev_ts).total_seconds()
                if gap <= 30:
                    if float(vib or 0) > THRESH:
                        operating_sec += gap
                        if not in_cycle:
                            in_cycle = True
                            cycle_start = prev_ts
                    else:
                        idle_sec += gap
                        if in_cycle:
                            if (ts - cycle_start).total_seconds() >= 30:
                                cycles += 1
                            in_cycle = False
            prev_ts = ts

        # Energy
        cur.execute("""
            SELECT sensor_id, power, timestamp
            FROM voltage_data
            WHERE timestamp >= %s
            ORDER BY sensor_id, timestamp ASC
        """, (today_start,))
        energy_wh = 0.0
        sprev = {}
        for sid, pwr, ts in cur.fetchall():
            pwr = float(pwr or 0)
            if sid in sprev:
                pp, pt = sprev[sid]
                gap = (ts - pt).total_seconds()
                if gap <= 30:
                    energy_wh += ((pwr + pp) / 2) * (gap / 3600)
            sprev[sid] = (pwr, ts)

        cur.close()

        kpi = {
            'operating_time': round(operating_sec / 3600, 2),
            'idle_time':      round(idle_sec      / 3600, 2),
            'cycles_today':   cycles,
            'energy_used':    round(energy_wh / 1000, 3)
        }
        log.debug(f'📊  KPI calculated  →  '
                  f'op={kpi["operating_time"]}hrs  '
                  f'idle={kpi["idle_time"]}hrs  '
                  f'cycles={kpi["cycles_today"]}  '
                  f'energy={kpi["energy_used"]}kWh')
        return kpi

    except Exception as e:
        log.error(f'📊  calculate_kpi_today ERROR  →  {e}')
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
    log.info('📡  GET /api/vibration  →  processing request ...')

    rec  = get_latest_vibration()
    volt = get_latest_voltages()
    kpi  = calculate_kpi_today()

    if rec and (datetime.now() - rec['timestamp']) < timedelta(seconds=10):
        age_sec = (datetime.now() - rec['timestamp']).total_seconds()
        log.info(f'📡  Vibration ONLINE  →  '
                 f'vib={rec["total_vibration"]:.2f} mm/s  '
                 f'temp={rec["temperature"]:.1f}°C  '
                 f'age={age_sec:.1f}s  '
                 f'velocity=({rec["velocity"]["x"]:.2f}, '
                 f'{rec["velocity"]["y"]:.2f}, '
                 f'{rec["velocity"]["z"]:.2f})')

        response = {
            'status':          'online',
            'total_vibration': rec['total_vibration'],
            'temperature':     rec['temperature'],
            'velocity':        rec['velocity'],
            'timestamp':       rec['timestamp'].isoformat()
        }

        # Queue payload for cloud sync
        log.debug('☁️   Building cloud payload ...')
        payload = build_payload(
            vib_rows  = [rec],
            volt_rows = volt,
            oil_rows  = [],
            kpi       = kpi
        )
        queued = enqueue(payload)
        if queued:
            log.info('☁️   Payload queued for cloud sync  →  ✅ success')
        else:
            log.warning('☁️   Payload queue FAILED  →  ⚠️ will not be synced')

        log.info('📡  Response sent  →  status=online')
        return jsonify(response)

    else:
        if not rec:
            log.warning('📡  Vibration OFFLINE  →  no records in DB')
        else:
            age_sec = (datetime.now() - rec['timestamp']).total_seconds()
            log.warning(f'📡  Vibration OFFLINE  →  '
                        f'last record is {age_sec:.1f}s old (threshold=10s)')

        log.info('📡  Response sent  →  status=offline')
        return jsonify({
            'status': 'offline',
            'total_vibration': 0,
            'temperature': 0,
            'velocity': {'x': 0, 'y': 0, 'z': 0}
        })


@app.route('/api/voltages')
def voltages():
    log.info('🔋  GET /api/voltages  →  processing request ...')
    recs = get_latest_voltages()
    now  = datetime.now()
    result = []

    for r in recs:
        age_sec = (now - r['timestamp']).total_seconds()
        status  = 'online' if age_sec < 10 else 'offline'
        r['status'] = status
        result.append(r)
        log.debug(f'🔋  sensor_id={r["sensor_id"]}  '
                  f'voltage={r["voltage"]:.2f}V  '
                  f'current={r["current"]:.2f}A  '
                  f'status={status}  age={age_sec:.1f}s')

    online_count = sum(1 for r in result if r['status'] == 'online')
    log.info(f'🔋  Response sent  →  '
             f'{len(result)} sensor(s)  online={online_count}  offline={len(result)-online_count}')
    return jsonify(result)


@app.route('/api/voltage/<int:sensor_id>')
def voltage_sensor(sensor_id):
    log.info(f'🔋  GET /api/voltage/{sensor_id}  →  processing request ...')
    recs = get_latest_voltages()

    for r in recs:
        if r['sensor_id'] == sensor_id:
            age_sec = (datetime.now() - r['timestamp']).total_seconds()
            online  = age_sec < 10
            status  = 'online' if online else 'offline'
            log.info(f'🔋  sensor_id={sensor_id}  '
                     f'voltage={r["voltage"]:.2f}V  '
                     f'current={r["current"]:.2f}A  '
                     f'status={status}  age={age_sec:.1f}s')
            return jsonify({**r, 'status': status})

    log.warning(f'🔋  sensor_id={sensor_id}  →  NOT FOUND in DB')
    return jsonify({'status': 'offline', 'voltage': 0, 'current': 0, 'power': 0, 'energy': 0})


@app.route('/api/kpi')
def kpi():
    log.info('📊  GET /api/kpi  →  processing request ...')
    data = calculate_kpi_today()
    if data:
        log.info(f'📊  Response sent  →  '
                 f'op={data["operating_time"]}hrs  '
                 f'idle={data["idle_time"]}hrs  '
                 f'cycles={data["cycles_today"]}  '
                 f'energy={data["energy_used"]}kWh')
        return jsonify(data)
    else:
        log.warning('📊  KPI calculation returned None  →  sending zeros')
        return jsonify({'operating_time': 0, 'idle_time': 0,
                        'cycles_today': 0, 'energy_used': 0})


# ════════════════════════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    log.info('=' * 55)
    log.info('🚀  Gear IQ API Server  STARTING')
    log.info(f'    DB      : {DB_CONFIG["dbname"]}@{DB_CONFIG["host"]}:{DB_CONFIG["port"]}')
    log.info(f'    Host    : 0.0.0.0:5000')
    log.info('=' * 55)

    # Quick DB check on startup
    conn = get_db_connection()
    if conn:
        log.info('🗄️  DB startup check  →  ✅ connected')
        conn.close()
    else:
        log.critical('🗄️  DB startup check  →  ❌ FAILED — check DB_CONFIG')

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
@app.route('/api/voltages')
def voltages():
    recs = get_latest_voltages()
    now = datetime.now()
    result = []
    for r in recs:
        r['status'] = 'online' if (now - r['timestamp']) < timedelta(seconds=10) else 'offline'
        result.append(r)
    return jsonify(result)

@app.route('/api/voltage/<int:sensor_id>')
def voltage_sensor(sensor_id):
    recs = get_latest_voltages()
    for r in recs:
        if r['sensor_id'] == sensor_id:
            now = datetime.now()
            online = (now - r['timestamp']) < timedelta(seconds=10)
            return jsonify({**r, 'status': 'online' if online else 'offline'})
    return jsonify({'status': 'offline', 'voltage': 0, 'current': 0, 'power': 0, 'energy': 0})


@app.route('/api/kpi')
def kpi():
    data = calculate_kpi_today() 
    if not data:
        return jsonify({'operating_time': 0, 'idle_time': 0,
                        'cycles_today': 0,   'energy_used': 0})
    return jsonify(data)


if __name__ == '__main__':
    print("🚀 Multi-Voltage API Server")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
