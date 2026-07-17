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
from config import DEVICE_ID, HOSTNAME, LOCATION  # ← add
from constants import VERSION  # ← add
from fault_codes import detect_faults, fault_summary
import logging

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

def get_latest_temperatures():
    conn = get_db_connection()
    if not conn: return []
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
        return [{
            'sensor_id':   r[0],
            'temperature': r[1],
            'status':      r[2],
            'timestamp':   r[3]
        } for r in rows]
    except Exception as e:
        print(f'[DB] get_latest_temperatures ERROR → {e}')
        return []
    finally:
        conn.close()



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

@app.route('/api/vibration')
def vibration():
    rec  = get_latest_vibration()
    volt = get_latest_voltages()
    data = calculate_kpi_today()

    if rec and (datetime.now() - rec['timestamp']) < timedelta(seconds=10):

        response = { 
            'status':          'online',
            'total_vibration': rec['total_vibration'],
            'temperature':     rec['temperature'],
            'velocity':        rec['velocity'],
            'timestamp':       rec['timestamp'].isoformat()
        }

        # Queue for cloud — wrapped so it never crashes the API
        try:
            payload = build_payload(
                vib_rows  = [rec],
                volt_rows = volt,
                oil_rows  = [],
                kpi       = data
            )
            enqueue(payload)
        except Exception as e:
            print(f'[cloud_sync] enqueue failed: {e}')  # log but don't crash

        return jsonify(response)

    else:
        return jsonify({
            'status': 'offline',
            'total_vibration': 0,
            'temperature': 0,
            'velocity': {'x': 0, 'y': 0, 'z': 0}
        })
    

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

@app.route('/api/device')
def device_info():
    return jsonify({
        'device_id': DEVICE_ID,
        'location':  LOCATION,
        'hostname':  HOSTNAME,
        'version':   VERSION
    })

@app.route('/api/temperature')
def temperature():
    recs = get_latest_temperatures()
    now  = datetime.now()
    result = []
    for r in recs:
        age    = (now - r['timestamp']).total_seconds()
        status = 'online' if age < 10 else 'offline'
        result.append({**r, 'status': status, 'timestamp': r['timestamp'].isoformat()})
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
 
    log.info(f'⚠️   Faults detected  →  '
             f'total={summary["total"]}  '
             f'critical={summary["critical"]}  '
             f'warning={summary["warning"]}  '
             f'status={summary["status"]}')
 
    if active_faults:
        for f in active_faults:
            log.warning(f'    [{f["severity"]}] {f["code"]}  {f["oem_desc"]}  →  {f["value"]}')
 
    return jsonify(summary)
 


if __name__ == '__main__':
    # ── Clean old records every time server starts ──
    print('[Startup] Cleaning old records ...')
    delete_old_voltage_records()
    delete_old_vibration_records()
    print('[Startup] Cleanup done ✅')
    print("🚀 Multi-Voltage API Server")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
