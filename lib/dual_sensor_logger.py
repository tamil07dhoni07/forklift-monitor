#!/usr/bin/env python3
# ============================================
# INTEGRATED FORKLIFT MONITOR - DUAL INTERFACE
# RS232: Fuel Level Sensor (Code 1)
# RS485: Multi-Sensor Logger (Code 2)
# BOTH INTERFACES RUNNING SIMULTANEOUSLY
# ============================================

import time
import minimalmodbus
import serial
import math
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime
import smbus          # for ADS1115 current sensor
import socket
import subprocess
import threading
import queue
from threading import Thread, Lock

# ============================================================
# SECTION 1: SINGLE DATABASE CONFIGURATION
# ============================================================

# Single database configuration - defined once
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'root',
    'database': 'gearid_db'  # Database name included here
}

# Admin connection (for database creation/checking)
# Uses 'postgres' default database for admin operations
ADMIN_DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'root',
    'database': 'postgres'
}

# Database connection pool (for reusing connections)
_db_pool = []
_pool_lock = Lock()
MAX_POOL_SIZE = 5

# ============================================================
# SECTION 2: SHARED DATABASE FUNCTIONS (REFACTORED)
# ============================================================

def get_db_connection():
    """
    Get a database connection from the pool or create a new one.
    Reuses existing connections to avoid duplication.
    """
    with _pool_lock:
        # Try to reuse an existing connection from the pool
        while _db_pool:
            conn = _db_pool.pop()
            try:
                # Check if connection is still valid
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return conn
            except Exception:
                # Connection is dead, discard it
                try:
                    conn.close()
                except:
                    pass
                continue
    
    # No valid connection available, create a new one
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"⚠️ DB connection error: {e}")
        return None

def return_db_connection(conn):
    """Return a connection to the pool for reuse"""
    if conn:
        with _pool_lock:
            if len(_db_pool) < MAX_POOL_SIZE:
                _db_pool.append(conn)
            else:
                # Pool is full, close the connection
                try:
                    conn.close()
                except:
                    pass

def execute_db_query(query, params=None, fetch_one=False, fetch_all=False):
    """
    Execute a database query with automatic connection management.
    Reuses connections from the pool.
    
    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)
        fetch_one: Return single row
        fetch_all: Return all rows
    
    Returns:
        Query result or None
    """
    conn = get_db_connection()
    if not conn:
        print("⚠️ DB connection failed")
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = None  # For INSERT/UPDATE/DELETE
        
        conn.commit()
        cursor.close()
        return result
    except Exception as e:
        print(f"⚠️ DB query error: {e}")
        try:
            conn.rollback()
        except:
            pass
        return None
    finally:
        return_db_connection(conn)

def create_database_if_not_exists():
    """Check if database exists, create it if it doesn't"""
    try:
        # Use admin connection to check/create database
        admin_conn = psycopg2.connect(**ADMIN_DB_CONFIG)
        admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = admin_conn.cursor()
        
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG['database'],))
        exists = cur.fetchone()
        
        if not exists:
            print(f"📋 Creating database: {DB_CONFIG['database']}")
            cur.execute(f"CREATE DATABASE {DB_CONFIG['database']}")
            print(f"✅ Database {DB_CONFIG['database']} created successfully")
        else:
            print(f"✅ Database {DB_CONFIG['database']} already exists")
        
        cur.close()
        admin_conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Database creation/check error: {e}")
        return False

def ensure_table_exists(table_name, create_query):
    """Check if table exists, create it if it doesn't"""
    try:
        # Use the shared connection via execute_db_query
        result = execute_db_query(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
            (table_name,),
            fetch_one=True
        )
        
        if result is None:
            return False
            
        exists = result[0]
        
        if not exists:
            print(f"📋 Creating table: {table_name}")
            execute_db_query(create_query)
            print(f"✅ Table {table_name} created successfully")
        else:
            print(f"✅ Table {table_name} already exists")
        
        return True
    except Exception as e:
        print(f"⚠️ Error checking/creating table {table_name}: {e}")
        return False

# Added: Initialize all tables including fuel level sensor table
def init_all_tables():
    """Initialize all required tables if they don't exist"""
    tables = {
        'vibration_sensor_data': """
            CREATE TABLE vibration_sensor_data (
                id SERIAL PRIMARY KEY,
                acceleration_x FLOAT,
                acceleration_y FLOAT,
                acceleration_z FLOAT,
                angular_velocity_x FLOAT,
                angular_velocity_y FLOAT,
                angular_velocity_z FLOAT,
                velocity_x FLOAT,
                velocity_y FLOAT,
                velocity_z FLOAT,
                total_vibration FLOAT,
                temperature FLOAT,
                status VARCHAR(10) DEFAULT 'OFF',
                issync INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        'voltage_data': """
            CREATE TABLE voltage_data (
                id SERIAL PRIMARY KEY,
                sensor_id INTEGER,
                voltage FLOAT,
                current FLOAT,
                power FLOAT,
                energy FLOAT,
                status VARCHAR(10) DEFAULT 'OFF',
                issync INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        'temperature_data': """
            CREATE TABLE temperature_data (
                id SERIAL PRIMARY KEY,
                sensor_id INTEGER,
                temperature FLOAT,
                status VARCHAR(10) DEFAULT 'OFF',
                issync INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        'current_sensor_data': """
            CREATE TABLE current_sensor_data (
                id SERIAL PRIMARY KEY,
                raw_adc INTEGER,
                voltage_v FLOAT,
                current_a FLOAT,
                status VARCHAR(10) DEFAULT 'OFF',
                issync INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        'status_details': """
            CREATE TABLE status_details (
                id SERIAL PRIMARY KEY,
                sensor_id VARCHAR(50) NOT NULL,
                status VARCHAR(10) NOT NULL,
                issync INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        'alerts': """
            CREATE TABLE alerts (
                id SERIAL PRIMARY KEY,
                type VARCHAR(10) NOT NULL,
                sensor VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                value TEXT,
                resolved INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                is_sync INTEGER NOT NULL DEFAULT 0,
                sync_time TIMESTAMP
            )
        """,
		 'cloud_queue': """
           CREATE TABLE IF NOT EXISTS cloud_sync_queue (
                id          SERIAL       PRIMARY KEY,
                payload     JSONB        NOT NULL,
                is_sync     INTEGER      NOT NULL DEFAULT 0,
                created_at  TIMESTAMP    NOT NULL DEFAULT NOW())
        """,
        'fuel_level_sensor_data': """
            CREATE TABLE fuel_level_sensor_data (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                temperature FLOAT,
                raw_distance_mm FLOAT,
                fuel_level_cm FLOAT,
                oil_height_mm FLOAT,
                volume_ml FLOAT,
                rounded_volume_l FLOAT,
                status VARCHAR(10) DEFAULT 'ON',
                issync INTEGER DEFAULT 0
            )
        """
    }

    for table_name, create_query in tables.items():
        if not ensure_table_exists(table_name, create_query):
            print(f"⚠️ Failed to initialize table: {table_name}")
            return False

    # Create indexes (using the shared connection)
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_status_details_sensor_id ON status_details (sensor_id)",
        "CREATE INDEX IF NOT EXISTS idx_status_details_created_at ON status_details (created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_status_details_issync ON status_details (issync)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts (resolved)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_is_sync ON alerts (is_sync)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (type)",
        "CREATE INDEX IF NOT EXISTS idx_vibration_issync ON vibration_sensor_data (issync)",
        "CREATE INDEX IF NOT EXISTS idx_voltage_issync ON voltage_data (issync)",
        "CREATE INDEX IF NOT EXISTS idx_temperature_issync ON temperature_data (issync)",
        "CREATE INDEX IF NOT EXISTS idx_current_issync ON current_sensor_data (issync)",
        "CREATE INDEX IF NOT EXISTS idx_fuel_level_timestamp ON fuel_level_sensor_data (timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_fuel_level_issync ON fuel_level_sensor_data (issync)"
    ]

    for idx_query in index_queries:
        try:
            execute_db_query(idx_query)
        except Exception as e:
            print(f"⚠️ Index creation warning: {e}")

    print("✅ All tables and indexes initialized successfully")
    return True

# Added: Insert fuel level data from RS232 (refactored to use shared connection)
def insert_fuel_level_data(temperature, raw_distance_mm, fuel_level_cm,
                          oil_height_mm, volume_ml, rounded_volume_l):
    """Insert fuel level sensor readings from RS232 into database"""
    try:
        query = """
            INSERT INTO fuel_level_sensor_data (
                timestamp,
                temperature,
                raw_distance_mm,
                fuel_level_cm,
                oil_height_mm,
                volume_ml,
                rounded_volume_l,
                status,
                issync
            ) VALUES (CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s, 'ON', 0)
        """
        params = (temperature, raw_distance_mm, fuel_level_cm, 
                 oil_height_mm, volume_ml, rounded_volume_l)
        
        result = execute_db_query(query, params)
        return result is not None  # execute_db_query returns None on success
    except Exception as e:
        print(f"⚠️ Fuel level data insertion error: {e}")
        return False

# ============================================================
# SECTION 3: RS232 - FUEL LEVEL SENSOR (FROM CODE 1)
# ============================================================

# ============ RS232 CONFIGURATION ============
# Changed: Renamed PORT to RS232_PORT for clarity
RS232_PORT = "/dev/ttyS9"
RS232_BAUD = 9600
RS232_SLAVE_ID = 1

# ============ RS232 TANK CALIBRATION ============
TANK_AREA_MM2 = 32195      # Calibrated area in mm²
CALIBRATION_OFFSET = 28    # mm (raw to actual height)

# ============ RS232 FUEL LEVEL CM CALCULATION ============
CALIBRATION_FACTOR = 175.0 / 145.3  # = 1.2044

# ============ RS232 MODBUS CRC ============
def crc16_rs232(data):
    """CRC16 calculation for RS232 fuel sensor"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, "little")

# ============ RS232 READ FUEL LEVEL DATA ============
def read_fuel_level_rs232():
    """Read fuel level sensor data from RS232 port"""
    cmd = bytes([RS232_SLAVE_ID, 0x03, 0x00, 0xFF, 0x00, 0x1E])
    cmd += crc16_rs232(cmd)

    try:
        ser = serial.Serial(RS232_PORT, RS232_BAUD, timeout=1)
        ser.write(cmd)
        resp = ser.read(100)
        ser.close()

        if len(resp) < 5:
            return None

        if crc16_rs232(resp[:-2]) != resp[-2:]:
            return None

        data = resp[3:-2]

        distance_raw = (data[2] << 8) | data[3] if len(data) > 3 else None
        temp_raw = (data[4] << 8) | data[5] if len(data) > 5 else None
        runtime_hours = (data[6] << 8) | data[7] if len(data) > 7 else None
        runtime_min = (data[8] << 8) | data[9] if len(data) > 9 else None
        signal_quality = (data[26] << 8) | data[27] if len(data) > 27 else None
        signal_mirror = (data[58] << 8) | data[59] if len(data) > 59 else None

        # CM CALCULATION: Apply the calibration factor
        distance_mm_raw = distance_raw / 10.0 if distance_raw else None

        if distance_mm_raw is not None:
            distance_calibrated_mm = distance_mm_raw * CALIBRATION_FACTOR
            distance_calibrated_mm = max(0, distance_calibrated_mm)
            fuel_level_cm = distance_calibrated_mm / 10.0
        else:
            fuel_level_cm = None

        # Calculate oil height and volume
        if distance_mm_raw is not None:
            oil_height = distance_mm_raw + CALIBRATION_OFFSET
            volume_litres = (TANK_AREA_MM2 * oil_height) / 1000000
            volume_ml = volume_litres * 1000
        else:
            oil_height = None
            volume_litres = None
            volume_ml = None

        return {
            'distance_raw': distance_raw,
            'distance_mm': distance_mm_raw,
            'temperature_raw': temp_raw,
            'temperature_c': temp_raw / 10.0 if temp_raw else None,
            'runtime_hours': runtime_hours,
            'runtime_minutes': runtime_min,
            'signal_quality': signal_quality,
            'signal_mirror': signal_mirror,
            'fuel_level_cm': fuel_level_cm,
            'oil_height_mm': oil_height,
            'volume_ml': volume_ml,
            'volume_litres': volume_litres
        }
    except Exception as e:
        print(f"⚠️ RS232 Fuel sensor error: {e}")
        return None

# ============================================================
# SECTION 4: RS485 - MULTI-SENSOR LOGGER (FROM CODE 2)
# ============================================================

# ========== RS485 CONFIGURATION ==========
RS485_PORT = "/dev/ttyUSB0"

# ---- Vibration ----
VIBRATION_SLAVE = 80
VIBRATION_STOPBITS = 1

# ---- Voltage sensors ----
VOLTAGE_CONFIG = {
    6: 1,   # Sensor 3 (stopbits=1)
    2: 2,   # Sensor 2 (stopbits=2)
    3: 2,   # Sensor 1 (stopbits=2)
    4: 1,   # Sensor 4 (stopbits=1)
}
VOLTAGE_SLAVES = list(VOLTAGE_CONFIG.keys())

# ---- PT100 Temperature (slave 1) ----
PT100_SLAVE = 1
PT100_STOPBITS = 1
PT100_CHANNEL_MAP = {
    6: 0,   # PT1 -> register 0 (sensor ID 6)
    2: 1,   # PT2 -> register 1 (sensor ID 2)
    3: 2,   # PT3 -> register 2 (sensor ID 3)
    4: 3,   # PT4 -> register 3 (sensor ID 4)
}
PT100_CHANNELS = list(PT100_CHANNEL_MAP.keys())

# ---- Current (ADS1115 via I2C) ----
ADS_BUS = 1
ADS_ADDR = 0x48
ADS_CONFIG = 0xC383
CURRENT_OFFSET_V = 2.509
CURRENT_SENSITIVITY = 0.004545
CURRENT_INVERT_SIGN = True

# ---- Serial & DB ----
RS485_BAUDRATE = 9600
RS485_TIMEOUT = 1.0
LOG_INTERVAL = 2

# ---- Status tracking ----
STATUS_UPDATE_INTERVAL = 1
WIFI_CHECK_INTERVAL = 2

# ============================================================
# SECTION 5: RS485 - STATUS TRACKING (FROM CODE 2)
# ============================================================

class StatusTracker:
    def __init__(self):
        pt100_sensor_ids = [f'pt100_{ch}' for ch in PT100_CHANNELS]
        self.sensors = (
            ['vibration'] +
            [f'voltage_{slave}' for slave in VOLTAGE_SLAVES] +
            pt100_sensor_ids +
            ['current', 'wifi', 'fuel_level_rs232']
        )
        self.status = {sensor: 'OFF' for sensor in self.sensors}
        self.status['wifi'] = 'DISCONNECTED'
        self.status['fuel_level_rs232'] = 'OFF'
        self.last_update = time.time()
        self.last_wifi_check = 0
        self.current_wifi_status = 'DISCONNECTED'
        self.lock = Lock()

    def check_wifi(self):
        """Check Wi-Fi connectivity"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3
            )
            if result.returncode == 0:
                self.current_wifi_status = 'CONNECTED'
            else:
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '2', '192.168.1.1'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3
                )
                self.current_wifi_status = 'CONNECTED' if result.returncode == 0 else 'DISCONNECTED'
        except Exception:
            self.current_wifi_status = 'DISCONNECTED'

        with self.lock:
            self.status['wifi'] = self.current_wifi_status
        return self.current_wifi_status

    def update_sensor_status(self, sensor_name, is_working):
        """Update status for a specific sensor"""
        if sensor_name in self.status:
            with self.lock:
                self.status[sensor_name] = 'ON' if is_working else 'OFF'

    def get_all_status(self):
        """Get all current statuses including Wi-Fi"""
        with self.lock:
            return self.status.copy()

    def get_sensor_status(self, sensor_name):
        """Get status for a specific sensor"""
        with self.lock:
            return self.status.get(sensor_name, 'OFF')

    def get_status_list(self):
        """Get status as a list of dictionaries"""
        status_list = []
        with self.lock:
            for sensor_id, status_value in self.status.items():
                status_list.append({
                    'sensor_id': sensor_id,
                    'status': status_value
                })
        return status_list

    def should_update_db(self):
        """Check if it's time to update the database with status"""
        current_time = time.time()
        if current_time - self.last_update >= STATUS_UPDATE_INTERVAL:
            self.last_update = current_time
            return True
        return False

    def should_check_wifi(self):
        """Check if it's time to check Wi-Fi"""
        current_time = time.time()
        if current_time - self.last_wifi_check >= WIFI_CHECK_INTERVAL:
            self.last_wifi_check = current_time
            return True
        return False

def update_status_in_db(status_list):
    """Insert multiple status records with timestamps and issync=0"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        for status_item in status_list:
            cursor.execute("""
                INSERT INTO status_details (
                    sensor_id, status, issync, created_at
                ) VALUES (%s, %s, 0, CURRENT_TIMESTAMP)
            """, (
                status_item['sensor_id'],
                status_item['status']
            ))
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        return True
    except Exception as e:
        print(f"⚠️ Status insertion error: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False

# ============================================================
# SECTION 6: RS485 - SENSOR INITIALIZATION (FROM CODE 2)
# ============================================================

def init_vibration_rs485():
    try:
        inst = minimalmodbus.Instrument(RS485_PORT, VIBRATION_SLAVE)
        inst.serial.baudrate = RS485_BAUDRATE
        inst.serial.stopbits = VIBRATION_STOPBITS
        inst.serial.timeout = RS485_TIMEOUT
        inst.mode = minimalmodbus.MODE_RTU
        temp = inst.read_register(0x40, 2)
        print(f"✅ RS485 Vibration (slave {VIBRATION_SLAVE}) found (temp: {temp}°C)")
        return inst
    except Exception as e:
        print(f"⚠️ RS485 Vibration init failed: {e}")
        return None

def init_voltage_rs485(slave_id, stopbits, retries=3):
    for attempt in range(retries):
        try:
            inst = minimalmodbus.Instrument(RS485_PORT, slave_id)
            inst.serial.baudrate = RS485_BAUDRATE
            inst.serial.stopbits = stopbits
            inst.serial.timeout = RS485_TIMEOUT
            inst.mode = minimalmodbus.MODE_RTU
            data = inst.read_registers(0, 2, functioncode=4)
            voltage = data[0] / 100.0
            print(f"✅ RS485 Voltage sensor (slave {slave_id}) found (voltage: {voltage}V)")
            return inst
        except Exception as e:
            print(f"⚠️ RS485 Voltage slave {slave_id} init attempt {attempt+1} failed: {e}")
            time.sleep(0.5)
    print(f"❌ RS485 Voltage slave {slave_id} not found after {retries} attempts.")
    return None

def init_pt100_rs485(retries=3):
    for attempt in range(retries):
        try:
            inst = minimalmodbus.Instrument(RS485_PORT, PT100_SLAVE)
            inst.serial.baudrate = RS485_BAUDRATE
            inst.serial.bytesize = 8
            inst.serial.parity = serial.PARITY_NONE
            inst.serial.stopbits = PT100_STOPBITS
            inst.serial.timeout = RS485_TIMEOUT
            inst.mode = minimalmodbus.MODE_RTU
            raw = inst.read_register(0, 0, functioncode=3)
            temp = raw / 10.0
            print(f"✅ RS485 PT100 (slave {PT100_SLAVE}) found (test temp: {temp:.1f}°C)")
            return inst
        except Exception as e:
            print(f"⚠️ RS485 PT100 init attempt {attempt+1} failed: {e}")
            time.sleep(0.5)
    print(f"❌ RS485 PT100 slave {PT100_SLAVE} not found after {retries} attempts.")
    return None

def read_pt100_channels_rs485(inst):
    result = {}
    for ch, reg in PT100_CHANNEL_MAP.items():
        try:
            raw = inst.read_register(reg, 0, functioncode=3)
            temp = raw / 10.0
            if 10 <= temp <= 50:
                result[ch] = round(temp, 1)
            else:
                result[ch] = None
        except Exception as e:
            print(f"⚠️ RS485 PT100 channel {ch} read error: {e}")
            result[ch] = None
    return result

def init_ads1115():
    try:
        bus = smbus.SMBus(ADS_BUS)
        bus.write_i2c_block_data(ADS_ADDR, 0x01,
                                 [(ADS_CONFIG >> 8) & 0xFF, ADS_CONFIG & 0xFF])
        time.sleep(0.01)
        data = bus.read_i2c_block_data(ADS_ADDR, 0x01, 2)
        config_read = (data[0] << 8) | data[1]
        if config_read != ADS_CONFIG:
            print(f"⚠️ ADS1115 config mismatch: wrote 0x{ADS_CONFIG:04X}, read 0x{config_read:04X}")
        else:
            print(f"✅ ADS1115 found on bus {ADS_BUS}, address 0x{ADS_ADDR:02X}")
        return bus
    except Exception as e:
        print(f"❌ ADS1115 init failed: {e}")
        return None

def read_ads1115(bus):
    try:
        bus.write_i2c_block_data(ADS_ADDR, 0x01,
                                 [(ADS_CONFIG >> 8) & 0xFF, ADS_CONFIG & 0xFF])
        time.sleep(0.01)
        data = bus.read_i2c_block_data(ADS_ADDR, 0x00, 2)
        raw = (data[0] << 8) | data[1]
        if raw & 0x8000:
            raw = raw - 65536
        voltage = raw * 0.000125
        current = (voltage - CURRENT_OFFSET_V) / CURRENT_SENSITIVITY
        if CURRENT_INVERT_SIGN:
            current = -current
        return raw, voltage, current
    except Exception as e:
        print(f"⚠️ ADS1115 read error: {e}")
        return None, None, None

def read_with_retry(inst, read_func, max_retries=2):
    for attempt in range(max_retries):
        try:
            return read_func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.2)
    return None

# ============================================================
# SECTION 7: RS232 - THREAD FUNCTION
# ============================================================

def rs232_thread(tracker, stop_event):
    """Thread function for RS232 fuel level sensor"""
    print("🔌 RS232 Thread started - Fuel Level Sensor")
    print(f"📡 RS232 Port: {RS232_PORT}")
    print(f"📡 RS232 Baud: {RS232_BAUD}")
    print(f"📡 RS232 Slave ID: {RS232_SLAVE_ID}")

    while not stop_event.is_set():
        try:
            data = read_fuel_level_rs232()

            if data and data['distance_mm'] is not None:
                tracker.update_sensor_status('fuel_level_rs232', True)

                temperature = data['temperature_c']
                raw_distance_mm = data['distance_mm']
                fuel_level_cm = data['fuel_level_cm']
                oil_height_mm = data['oil_height_mm']
                volume_ml = data['volume_ml']
                volume_litres = data['volume_litres']

                if insert_fuel_level_data(
                    temperature,
                    raw_distance_mm,
                    fuel_level_cm,
                    oil_height_mm,
                    volume_ml,
                    volume_litres
                ):
                    print("✅ RS232 Fuel level data saved to database")
                else:
                    print("⚠️ RS232 Failed to save fuel level data")

                print("=" * 60)
                print(f"[RS232] Temperature: {temperature:.1f} °C")
                print(f"[RS232] Runtime: {data['runtime_hours']}h {data['runtime_minutes']}m")
                print(f"[RS232] Signal Quality: {data['signal_quality']}")
                print(f"[RS232] Signal Mirror: {data['signal_mirror']}")
                print("-" * 60)
                print(f"[RS232] Raw Distance: {raw_distance_mm:.1f} mm")
                print(f"[RS232] Fuel Level (cm): {fuel_level_cm:.2f} cm")
                print(f"[RS232] Oil Height: {oil_height_mm:.1f} mm")
                print("-" * 60)
                print(f"[RS232] Volume: {volume_ml:,.0f} ml")
                print(f"[RS232] Volume: {volume_litres:.2f} L")
                print("=" * 60)
            else:
                tracker.update_sensor_status('fuel_level_rs232', False)
                print("[RS232] No data from fuel sensor")
                insert_fuel_level_data(None, None, None, None, None, None)

        except Exception as e:
            print(f"⚠️ RS232 Thread error: {e}")
            tracker.update_sensor_status('fuel_level_rs232', False)

        time.sleep(1)

# ============================================================
# SECTION 8: RS485 - MAIN FUNCTION (REFACTORED)
# ============================================================

def rs485_main_loop(tracker, stop_event):
    """Main loop for RS485 multi-sensor logger"""
    print("🔌 RS485 Thread started - Multi-Sensor Logger")
    print(f"📡 RS485 Port: {RS485_PORT}")
    print(f"📡 RS485 Vibration slave: {VIBRATION_SLAVE}")
    print(f"📡 RS485 Voltage slaves: {VOLTAGE_SLAVES}")
    print(f"📡 RS485 PT100 slave: {PT100_SLAVE}, channels: {PT100_CHANNELS}")
    print(f"📡 RS485 Current sensor: ADS1115 on bus {ADS_BUS}, address 0x{ADS_ADDR:02X}\n")

    # Initialize RS485 sensors
    vib_inst = init_vibration_rs485()
    time.sleep(0.5)

    vol_insts = {}
    for slave in VOLTAGE_SLAVES:
        stopbits = VOLTAGE_CONFIG[slave]
        inst = init_voltage_rs485(slave, stopbits)
        if inst:
            vol_insts[slave] = inst

    pt100_inst = init_pt100_rs485()
    ads_bus = init_ads1115()

    if not vib_inst and not vol_insts and not pt100_inst and not ads_bus:
        print("❌ RS485 No sensors found.")
        return

    print("\n✅ RS485 Logger running. Press Ctrl+C to stop.\n")

    while not stop_event.is_set():
        vib_data = None
        vol_data_list = []
        current_data = None
        pt100_data = None
        vibration_status = 'OFF'
        voltage_statuses = {}

        if tracker.should_check_wifi():
            tracker.check_wifi()
            print(f"📶 Wi-Fi: {tracker.current_wifi_status}")

        # ---- Read Vibration ----
        if vib_inst:
            try:
                vx = vib_inst.read_register(0x3A, 0)
                vy = vib_inst.read_register(0x3B, 0)
                vz = vib_inst.read_register(0x3C, 0)
                temp = vib_inst.read_register(0x40, 2)
                total_vib = round(math.sqrt(vx*vx + vy*vy + vz*vz), 2)
                vib_data = {
                    'vx': vx, 'vy': vy, 'vz': vz,
                    'total': total_vib,
                    'temp': round(temp, 2)
                }
                print(f"📊 RS485 VIB: {total_vib} mm/s | Temp: {temp}°C")
                tracker.update_sensor_status('vibration', True)
                vibration_status = 'ON'
            except Exception as e:
                print(f"⚠️ RS485 Vibration read error: {e}")
                tracker.update_sensor_status('vibration', False)
                vibration_status = 'OFF'

        time.sleep(0.1)

        # ---- Read Voltage Sensors ----
        for slave, inst in vol_insts.items():
            try:
                data = read_with_retry(inst, lambda: inst.read_registers(0, 6, functioncode=4))
                if data is None:
                    print(f"⚠️ RS485 Voltage slave {slave} read failed after retries")
                    tracker.update_sensor_status(f'voltage_{slave}', False)
                    voltage_statuses[slave] = 'OFF'
                    continue
                voltage = data[0] / 100.0
                current = data[1] / 100.0
                power_raw = (data[3] << 16) | data[2]
                power = power_raw / 10.0
                energy = (data[5] << 16) | data[4]
                vol_data = {
                    'sensor_id': slave,
                    'voltage': round(voltage, 2),
                    'current': round(current, 2),
                    'power': round(power, 1),
                    'energy': energy,
                    'status': 'ON'
                }
                vol_data_list.append(vol_data)
                print(f"⚡ RS485 VOLT{slave}: {voltage}V | Curr: {current}A | Power: {power}W")
                tracker.update_sensor_status(f'voltage_{slave}', True)
                voltage_statuses[slave] = 'ON'
            except Exception as e:
                print(f"⚠️ RS485 Voltage slave {slave} read error: {e}")
                tracker.update_sensor_status(f'voltage_{slave}', False)
                voltage_statuses[slave] = 'OFF'

        time.sleep(0.1)

        # ---- Read PT100 Temperatures ----
        if pt100_inst:
            pt100_data = read_pt100_channels_rs485(pt100_inst)
            if pt100_data:
                for ch, temp in pt100_data.items():
                    is_working = temp is not None
                    tracker.update_sensor_status(f'pt100_{ch}', is_working)
                    if is_working:
                        print(f"🌡️ RS485 PT{ch}: {temp:.1f}°C")
                    else:
                        print(f"🌡️ RS485 PT{ch}: No Sensor ❌")
            else:
                for ch in PT100_CHANNELS:
                    tracker.update_sensor_status(f'pt100_{ch}', False)
                print("⚠️ RS485 PT100 read failed entirely")

        time.sleep(0.1)

        # ---- Read Current (ADS1115) ----
        current_status = 'OFF'
        if ads_bus:
            raw_adc, voltage_v, current_a = read_ads1115(ads_bus)
            if raw_adc is not None:
                current_data = {
                    'raw_adc': raw_adc,
                    'voltage_v': round(voltage_v, 3),
                    'current_a': round(current_a, 3),
                    'status': 'ON'
                }
                print(f"🔌 RS485 CURRENT: {current_a:.3f} A (raw: {raw_adc}, V: {voltage_v:.3f} V)")
                tracker.update_sensor_status('current', True)
                current_status = 'ON'
            else:
                print("⚠️ RS485 Current read failed")
                tracker.update_sensor_status('current', False)
                current_status = 'OFF'

        # ---- Insert into DB (using shared connection) ----
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                if vib_data:
                    cursor.execute("""
                        INSERT INTO vibration_sensor_data (
                            acceleration_x, acceleration_y, acceleration_z,
                            angular_velocity_x, angular_velocity_y, angular_velocity_z,
                            velocity_x, velocity_y, velocity_z,
                            total_vibration, temperature, status, issync
                        ) VALUES (0,0,0, 0,0,0, %s,%s,%s, %s,%s, %s, 0)
                    """, (vib_data['vx'], vib_data['vy'], vib_data['vz'],
                          vib_data['total'], vib_data['temp'], vibration_status))

                for v in vol_data_list:
                    cursor.execute("""
                        INSERT INTO voltage_data (sensor_id, voltage, current, power, energy, status, issync)
                        VALUES (%s, %s, %s, %s, %s, %s, 0)
                    """, (v['sensor_id'], v['voltage'], v['current'], v['power'], v['energy'], v['status']))

                if pt100_data:
                    for ch, temp in pt100_data.items():
                        if temp is not None:
                            channel_status = tracker.get_sensor_status(f'pt100_{ch}')
                            cursor.execute("""
                                INSERT INTO temperature_data (sensor_id, temperature, status, issync)
                                VALUES (%s, %s, %s, 0)
                            """, (ch, temp, channel_status))

                if current_data:
                    cursor.execute("""
                        INSERT INTO current_sensor_data (raw_adc, voltage_v, current_a, status, issync)
                        VALUES (%s, %s, %s, %s, 0)
                    """, (current_data['raw_adc'], current_data['voltage_v'],
                          current_data['current_a'], current_data['status']))

                conn.commit()
                cursor.close()
                return_db_connection(conn)
            except Exception as e:
                print(f"⚠️ RS485 Data insertion error: {e}")
                try:
                    conn.rollback()
                except:
                    pass
                return_db_connection(conn)
        else:
            print("⚠️ RS485 DB connection failed – data not saved.")

        # ---- Update status table periodically ----
        if tracker.should_update_db():
            status_list = tracker.get_status_list()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n📊 STATUS UPDATE [{current_time}]:")
            print(f"{'Sensor':<20} | {'Status':<10}")
            print("-" * 35)
            for status_item in status_list:
                print(f"{status_item['sensor_id']:<20} | {status_item['status']:<10}")
            print()

            if update_status_in_db(status_list):
                print(f"✅ Status saved at {current_time} (issync=0)")
                print(f"   📝 Inserted {len(status_list)} status records")
            print()

        time.sleep(LOG_INTERVAL)

# ============================================================
# SECTION 9: MAIN - INTEGRATED APPLICATION
# ============================================================

def main():
    print("=" * 70)
    print("INTEGRATED FORKLIFT MONITOR - DUAL INTERFACE")
    print("=" * 70)
    print("RS232: Fuel Level Sensor (Code 1)")
    print("RS485: Multi-Sensor Logger (Code 2)")
    print("=" * 70)
    print()

    print("📦 Checking database...")
    if not create_database_if_not_exists():
        print("❌ Failed to create/check database. Exiting.")
        return

    print("\n📋 Checking tables...")
    if not init_all_tables():
        print("❌ Failed to initialize database tables. Exiting.")
        return

    tracker = StatusTracker()
    stop_event = threading.Event()

    print("\n🔌 Starting RS232 thread...")
    rs232_thread_obj = Thread(target=rs232_thread, args=(tracker, stop_event), daemon=True)
    rs232_thread_obj.start()
    print("✅ RS232 thread started")

    print("\n🔌 Starting RS485 thread...")
    rs485_thread_obj = Thread(target=rs485_main_loop, args=(tracker, stop_event), daemon=True)
    rs485_thread_obj.start()
    print("✅ RS485 thread started")

    print("\n" + "=" * 70)
    print("BOTH INTERFACES RUNNING SIMULTANEOUSLY")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    try:
        while True:
            time.sleep(1)
            if not rs232_thread_obj.is_alive():
                print("⚠️ RS232 thread died! Restarting...")
                rs232_thread_obj = Thread(target=rs232_thread, args=(tracker, stop_event), daemon=True)
                rs232_thread_obj.start()

            if not rs485_thread_obj.is_alive():
                print("⚠️ RS485 thread died! Restarting...")
                rs485_thread_obj = Thread(target=rs485_main_loop, args=(tracker, stop_event), daemon=True)
                rs485_thread_obj.start()

    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal. Shutting down...")
        stop_event.set()
        print("⏳ Waiting for threads to finish...")
        time.sleep(2)
        print("✅ Application stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Application terminated by user.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")