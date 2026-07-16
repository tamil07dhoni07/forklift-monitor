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

@app.route('/api/vibration')
def vibration():
    rec = get_latest_vibration()
    volt = get_latest_voltages()
    data = calculate_kpi_today() 

    if rec and (datetime.now() - rec['timestamp']) < timedelta(seconds=10):

        # ── existing response ──
        response = {
            'status': 'online',
            'total_vibration': rec['total_vibration'],
            'temperature': rec['temperature'],
            'velocity': rec['velocity'],
            'timestamp': rec['timestamp'].isoformat()
        }

        # ── add this: queue for cloud ──
        # payload = build_payload(
        #     vib_rows  = [rec],
        #     volt_rows = volt,
        #     oil_rows  = [],      # empty until oil sensor ready
        #     kpi       = data     # or pass kpi dict if you have it
        # )
        # enqueue(payload)         # saves to DB queue, daemon does the rest

        return jsonify(response)

    else:
        return jsonify({'status': 'offline', 'total_vibration': 0, 'temperature': 0, 'velocity': {'x':0,'y':0,'z':0}})

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
