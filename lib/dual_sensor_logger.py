#!/usr/bin/env python3
# ============================================
# FORKLIFT MONITOR - MULTI-SENSOR LOGGER
# 1 Vibration (ID 80) + 4 Voltage (IDs 6,2,3,4)
# + 1 Current (ADS1115) + 4 PT100 Temperatures (ID 1)
# WITH STATUS MONITORING - TIMESTAMPED
# AUTO DATABASE & TABLE CREATION
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
 
# ========== CONFIGURATION ==========
PORT = "/dev/ttyUSB0"
 
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
VOLTAGE_SLAVES = list(VOLTAGE_CONFIG.keys())   # [6, 2, 3, 4]
 
# ---- PT100 Temperature (slave 1) ----
PT100_SLAVE = 1
PT100_STOPBITS = 1
PT100_CHANNEL_MAP = {
    1: 0,   # PT1 -> register 0
    2: 1,   # PT2 -> register 1
    3: 2,   # PT3 -> register 2
    4: 3,   # PT4 -> register 3
}
PT100_CHANNELS = list(PT100_CHANNEL_MAP.keys())  # [1,2,3,4]
 
# ---- Current (ADS1115 via I2C) ----
ADS_BUS = 1                 # from `i2cdetect -y 1` â†’ address 0x48
ADS_ADDR = 0x48
ADS_CONFIG = 0xC383         # singleâ€‘shot, AIN0â€‘GND, Â±4.096V, 128 SPS
 
# Calibration values (update after running --calibrate-current)
CURRENT_OFFSET_V = 2.509          # zeroâ€‘current voltage
CURRENT_SENSITIVITY = 0.004545    # V/A (calculated from 0.22A test)
# Optional: invert sign if your reading is negative for positive current
CURRENT_INVERT_SIGN = True        # set True if you want positive for your direction
 
# ---- Serial & DB ----
BAUDRATE = 9600
TIMEOUT = 3.0
LOG_INTERVAL = 2
 
# Database configuration
DB_NAME = 'gearid_db'
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'root'
}
 
# Full DB config with database name (for connecting to specific database)
DB_CONFIG_WITH_DB = {
    'host': 'localhost',
    'port': 5432,
    'dbname': DB_NAME,
    'user': 'postgres',
    'password': 'root'
}
 
# ---- Status tracking ----
STATUS_UPDATE_INTERVAL = 10  # Update status table every 10 seconds (even if no data)
WIFI_CHECK_INTERVAL = 30     # Check Wi-Fi every 30 seconds
 
# ============================================================
 
# ========== DATABASE CREATION ==========
def create_database_if_not_exists():
    """Check if database exists, create it if it doesn't"""
    try:
        # Connect to default 'postgres' database
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dbname='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cur.fetchone()
        if not exists:
            print(f"ðŸ“‹ Creating database: {DB_NAME}")
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"âœ… Database {DB_NAME} created successfully")
        else:
            print(f"âœ… Database {DB_NAME} already exists")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"âš ï¸ Database creation/check error: {e}")
        return False
 
def get_db_connection():
    """Get database connection to the specific database"""
    try:
        return psycopg2.connect(**DB_CONFIG_WITH_DB)
    except Exception as e:
        print(f"âš ï¸ DB error: {e}")
        return None
 
# ========== TABLE CREATION ==========
def ensure_table_exists(table_name, create_query):
    """Check if table exists, create it if it doesn't"""
    conn = get_db_connection()
    if not conn:
        return False
 
    cur = conn.cursor()
    try:
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = %s
            )
        """, (table_name,))
        exists = cur.fetchone()[0]
 
        if not exists:
            print(f"ðŸ“‹ Creating table: {table_name}")
            cur.execute(create_query)
            conn.commit()
            print(f"âœ… Table {table_name} created successfully")
        else:
            print(f"âœ… Table {table_name} already exists")
 
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"âš ï¸ Error checking/creating table {table_name}: {e}")
        cur.close()
        conn.close()
        return False
 
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
        """
    }
 
    # Create tables
    for table_name, create_query in tables.items():
        if not ensure_table_exists(table_name, create_query):
            print(f"âš ï¸ Failed to initialize table: {table_name}")
            return False
 
    # Create indexes (IF NOT EXISTS is supported)
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
        "CREATE INDEX IF NOT EXISTS idx_current_issync ON current_sensor_data (issync)"
    ]
 
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        for idx_query in index_queries:
            try:
                cur.execute(idx_query)
                conn.commit()
            except Exception as e:
                print(f"âš ï¸ Index creation warning: {e}")
        cur.close()
        conn.close()
 
    print("âœ… All tables and indexes initialized successfully")
    return True
 
# ========== STATUS TRACKING ==========
class StatusTracker:
    def __init__(self):
        # Initialize status for all sensors
        self.sensors = [
            'vibration',
            'voltage_2',
            'voltage_3',
            'voltage_4',
            'voltage_6',
            'pt100',
            'current',
            'wifi'
        ]
        self.status = {sensor: 'OFF' for sensor in self.sensors}
        self.status['wifi'] = 'DISCONNECTED'
        self.last_update = time.time()
        self.last_wifi_check = 0
        self.current_wifi_status = 'DISCONNECTED'
 
    def check_wifi(self):
        """Check Wi-Fi connectivity by pinging gateway or 8.8.8.8"""
        try:
            # Try to ping Google DNS
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3
            )
            if result.returncode == 0:
                self.current_wifi_status = 'CONNECTED'
            else:
                # Try gateway as fallback
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '2', '192.168.1.1'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3
                )
                self.current_wifi_status = 'CONNECTED' if result.returncode == 0 else 'DISCONNECTED'
        except Exception:
            self.current_wifi_status = 'DISCONNECTED'
 
        self.status['wifi'] = self.current_wifi_status
        return self.current_wifi_status
 
    def update_sensor_status(self, sensor_name, is_working):
        """Update status for a specific sensor"""
        if sensor_name in self.status:
            self.status[sensor_name] = 'ON' if is_working else 'OFF'
 
    def update_pt100_status(self, pt100_data):
        """Update PT100 status based on whether at least one channel works"""
        if pt100_data:
            working = any(temp is not None for temp in pt100_data.values())
            self.update_sensor_status('pt100', working)
 
    def get_all_status(self):
        """Get all current statuses including Wi-Fi"""
        return self.status
 
    def get_sensor_status(self, sensor_name):
        """Get status for a specific sensor"""
        return self.status.get(sensor_name, 'OFF')
 
    def get_status_list(self):
        """Get status as a list of dictionaries for database insertion"""
        status_list = []
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
 
# ========== DATABASE FUNCTIONS ==========
def update_status_in_db(status_list):
    """Insert multiple status records with timestamps and issync=0"""
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        try:
            # Insert multiple records at once
            for status_item in status_list:
                cur.execute("""
                    INSERT INTO status_details (
                        sensor_id, status, issync, created_at
                    ) VALUES (%s, %s, 0, CURRENT_TIMESTAMP)
                """, (
                    status_item['sensor_id'],
                    status_item['status']
                ))
 
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"âš ï¸ Status insertion error: {e}")
            cur.close()
            conn.close()
            return False
    return False
 
def get_latest_status():
    """Get the latest status records from the database"""
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        try:
            # Get the latest status for each sensor
            cur.execute("""
                SELECT DISTINCT ON (sensor_id) 
                    sensor_id, status, issync, created_at
                FROM status_details
                ORDER BY sensor_id, created_at DESC
            """)
            result = cur.fetchall()
            cur.close()
            conn.close()
            return result
        except Exception as e:
            print(f"âš ï¸ Error fetching latest status: {e}")
            cur.close()
            conn.close()
            return None
    return None
 
def get_status_history(sensor_id=None, limit=10):
    """Get status history for a specific sensor or all sensors"""
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        try:
            if sensor_id:
                cur.execute("""
                    SELECT sensor_id, status, issync, created_at
                    FROM status_details
                    WHERE sensor_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (sensor_id, limit))
            else:
                cur.execute("""
                    SELECT sensor_id, status, issync, created_at
                    FROM status_details
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
            result = cur.fetchall()
            cur.close()
            conn.close()
            return result
        except Exception as e:
            print(f"âš ï¸ Error fetching status history: {e}")
            cur.close()
            conn.close()
            return None
    return None
 
# ========== INIT SENSORS ==========
def init_vibration():
    try:
        inst = minimalmodbus.Instrument(PORT, VIBRATION_SLAVE)
        inst.serial.baudrate = BAUDRATE
        inst.serial.stopbits = VIBRATION_STOPBITS
        inst.serial.timeout = TIMEOUT
        inst.mode = minimalmodbus.MODE_RTU
        temp = inst.read_register(0x40, 2)
        print(f"âœ… Vibration (slave {VIBRATION_SLAVE}) found (temp: {temp}Â°C)")
        return inst
    except Exception as e:
        print(f"âš ï¸ Vibration init failed: {e}")
        return None
 
def init_voltage(slave_id, stopbits, retries=3):
    for attempt in range(retries):
        try:
            inst = minimalmodbus.Instrument(PORT, slave_id)
            inst.serial.baudrate = BAUDRATE
            inst.serial.stopbits = stopbits
            inst.serial.timeout = TIMEOUT
            inst.mode = minimalmodbus.MODE_RTU
            data = inst.read_registers(0, 2, functioncode=4)
            voltage = data[0] / 100.0
            print(f"âœ… Voltage sensor (slave {slave_id}) found (voltage: {voltage}V)")
            return inst
        except Exception as e:
            print(f"âš ï¸ Voltage slave {slave_id} init attempt {attempt+1} failed: {e}")
            time.sleep(0.5)
    print(f"âŒ Voltage slave {slave_id} not found after {retries} attempts.")
    return None
 
def init_pt100(retries=3):
    """Initialize the PT100 instrument (slave 1)."""
    for attempt in range(retries):
        try:
            inst = minimalmodbus.Instrument(PORT, PT100_SLAVE)
            inst.serial.baudrate = BAUDRATE
            inst.serial.bytesize = 8
            inst.serial.parity = serial.PARITY_NONE
            inst.serial.stopbits = PT100_STOPBITS
            inst.serial.timeout = TIMEOUT
            inst.mode = minimalmodbus.MODE_RTU
            # Try reading one channel to verify communication
            raw = inst.read_register(0, 0, functioncode=3)
            temp = raw / 10.0
            print(f"âœ… PT100 (slave {PT100_SLAVE}) found (test temp: {temp:.1f}Â°C)")
            return inst
        except Exception as e:
            print(f"âš ï¸ PT100 init attempt {attempt+1} failed: {e}")
            time.sleep(0.5)
    print(f"âŒ PT100 slave {PT100_SLAVE} not found after {retries} attempts.")
    return None
 
def read_pt100_channels(inst):
    """Read all PT100 channels; returns dict {channel: temperature} or None on failure."""
    result = {}
    for ch, reg in PT100_CHANNEL_MAP.items():
        try:
            raw = inst.read_register(reg, 0, functioncode=3)
            temp = raw / 10.0
            # Apply a sanity check (optional)
            if 10 <= temp <= 50:
                result[ch] = round(temp, 1)
            else:
                result[ch] = None   # out-of-range indicates no sensor
        except Exception as e:
            print(f"âš ï¸ PT100 channel {ch} read error: {e}")
            result[ch] = None
    return result
 
def init_ads1115():
    """Initialize I2C bus for ADS1115 and verify communication."""
    try:
        bus = smbus.SMBus(ADS_BUS)
        # Write config and read back to confirm
        bus.write_i2c_block_data(ADS_ADDR, 0x01,
                                 [(ADS_CONFIG >> 8) & 0xFF, ADS_CONFIG & 0xFF])
        time.sleep(0.01)
        data = bus.read_i2c_block_data(ADS_ADDR, 0x01, 2)
        config_read = (data[0] << 8) | data[1]
        if config_read != ADS_CONFIG:
            print(f"âš ï¸ ADS1115 config mismatch: wrote 0x{ADS_CONFIG:04X}, read 0x{config_read:04X}")
        else:
            print(f"âœ… ADS1115 found on bus {ADS_BUS}, address 0x{ADS_ADDR:02X}")
        return bus
    except Exception as e:
        print(f"âŒ ADS1115 init failed: {e}")
        return None
 
# ========== CURRENT SENSOR READ FUNCTION ==========
def read_ads1115(bus):
    """Read one sample from ADS1115; returns (raw_adc, voltage_V, current_A) or (None,None,None)."""
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
        print(f"âš ï¸ ADS1115 read error: {e}")
        return None, None, None
 
# ========== HELPER ==========
def read_with_retry(inst, read_func, max_retries=2):
    for attempt in range(max_retries):
        try:
            return read_func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.2)
    return None
 
# ========== MAIN LOOP ==========
def main():
    print("ðŸ”Œ Multi-Sensor Logger with Status Monitoring (Timestamped)")
    print(f"ðŸ“¡ Vibration slave: {VIBRATION_SLAVE}")
    print(f"ðŸ“¡ Voltage slaves: {VOLTAGE_SLAVES}")
    print(f"ðŸ“¡ PT100 slave: {PT100_SLAVE}, channels: {PT100_CHANNELS}")
    print(f"ðŸ“¡ Current sensor: ADS1115 on bus {ADS_BUS}, address 0x{ADS_ADDR:02X}\n")
 
    # Step 1: Create database if it doesn't exist
    print("ðŸ“¦ Checking database...")
    if not create_database_if_not_exists():
        print("âŒ Failed to create/check database. Exiting.")
        return
 
    # Step 2: Initialize all tables
    print("\nðŸ“‹ Checking tables...")
    if not init_all_tables():
        print("âŒ Failed to initialize database tables. Exiting.")
        return
 
    # Step 3: Initialize status tracker
    tracker = StatusTracker()
 
    # Step 4: Initialize sensors
    print("\nðŸ”Œ Initializing sensors...")
    vib_inst = init_vibration()
    time.sleep(0.5)
 
    vol_insts = {}
    for slave in VOLTAGE_SLAVES:
        stopbits = VOLTAGE_CONFIG[slave]
        inst = init_voltage(slave, stopbits)
        if inst:
            vol_insts[slave] = inst
 
    pt100_inst = init_pt100()
    ads_bus = init_ads1115()
 
    if not vib_inst and not vol_insts and not pt100_inst and not ads_bus:
        print("âŒ No sensors found. Exiting.")
        return
 
    print("\nâœ… Logger running. Press Ctrl+C to stop.\n")
 
    while True:
        vib_data = None
        vol_data_list = []
        current_data = None
        pt100_data = None
        vibration_status = 'OFF'
        voltage_statuses = {}
 
        # Check Wi-Fi status periodically
        if tracker.should_check_wifi():
            tracker.check_wifi()
            print(f"ðŸ“¶ Wi-Fi: {tracker.current_wifi_status}")
 
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
                print(f"ðŸ“Š VIB: {total_vib} mm/s | Temp: {temp}Â°C")
                tracker.update_sensor_status('vibration', True)
                vibration_status = 'ON'
            except Exception as e:
                print(f"âš ï¸ Vibration read error: {e}")
                tracker.update_sensor_status('vibration', False)
                vibration_status = 'OFF'
 
        time.sleep(0.1)
 
        # ---- Read Voltage Sensors ----
        for slave, inst in vol_insts.items():
            try:
                data = read_with_retry(inst, lambda: inst.read_registers(0, 6, functioncode=4))
                if data is None:
                    print(f"âš ï¸ Voltage slave {slave} read failed after retries")
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
                print(f"âš¡ VOLT{slave}: {voltage}V | Curr: {current}A | Power: {power}W")
                tracker.update_sensor_status(f'voltage_{slave}', True)
                voltage_statuses[slave] = 'ON'
            except Exception as e:
                print(f"âš ï¸ Voltage slave {slave} read error: {e}")
                tracker.update_sensor_status(f'voltage_{slave}', False)
                voltage_statuses[slave] = 'OFF'
 
        time.sleep(0.1)
 
        # ---- Read PT100 Temperatures ----
        pt100_status = 'OFF'
        if pt100_inst:
            pt100_data = read_pt100_channels(pt100_inst)
            if pt100_data:
                any_working = False
                for ch, temp in pt100_data.items():
                    if temp is not None:
                        print(f"ðŸŒ¡ï¸ PT{ch}: {temp:.1f}Â°C")
                        any_working = True
                    else:
                        print(f"ðŸŒ¡ï¸ PT{ch}: No Sensor âŒ")
                tracker.update_sensor_status('pt100', any_working)
                pt100_status = 'ON' if any_working else 'OFF'
            else:
                tracker.update_sensor_status('pt100', False)
                pt100_status = 'OFF'
 
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
                print(f"ðŸ”Œ CURRENT: {current_a:.3f} A (raw: {raw_adc}, V: {voltage_v:.3f} V)")
                tracker.update_sensor_status('current', True)
                current_status = 'ON'
            else:
                print("âš ï¸ Current read failed")
                tracker.update_sensor_status('current', False)
                current_status = 'OFF'
 
        # ---- Insert into DB ----
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            try:
                # Insert vibration data with status
                if vib_data:
                    cur.execute("""
                        INSERT INTO vibration_sensor_data (
                            acceleration_x, acceleration_y, acceleration_z,
                            angular_velocity_x, angular_velocity_y, angular_velocity_z,
                            velocity_x, velocity_y, velocity_z,
                            total_vibration, temperature, status, issync
                        ) VALUES (0,0,0, 0,0,0, %s,%s,%s, %s,%s, %s, 0)
                    """, (vib_data['vx'], vib_data['vy'], vib_data['vz'],
                          vib_data['total'], vib_data['temp'], vibration_status))
 
                # Insert voltage data with status
                for v in vol_data_list:
                    cur.execute("""
                        INSERT INTO voltage_data (sensor_id, voltage, current, power, energy, status, issync)
                        VALUES (%s, %s, %s, %s, %s, %s, 0)
                    """, (v['sensor_id'], v['voltage'], v['current'], v['power'], v['energy'], v['status']))
 
                # Insert temperature data with status
                if pt100_data:
                    for ch, temp in pt100_data.items():
                        if temp is not None:
                            cur.execute("""
                                INSERT INTO temperature_data (sensor_id, temperature, status, issync)
                                VALUES (%s, %s, %s, 0)
                            """, (ch, temp, pt100_status))
 
                # Insert current data with status
                if current_data:
                    cur.execute("""
                        INSERT INTO current_sensor_data (raw_adc, voltage_v, current_a, status, issync)
                        VALUES (%s, %s, %s, %s, 0)
                    """, (current_data['raw_adc'], current_data['voltage_v'], 
                          current_data['current_a'], current_data['status']))
 
                conn.commit()
            except Exception as e:
                print(f"âš ï¸ Data insertion error: {e}")
            finally:
                cur.close()
                conn.close()
        else:
            print("âš ï¸ DB connection failed â€“ data not saved.")
 
        # ---- Update status table periodically ----
        if tracker.should_update_db():
            status_list = tracker.get_status_list()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\nðŸ“Š STATUS UPDATE [{current_time}]:")
            # Print status in a table-like format
            print(f"{'Sensor':<15} | {'Status':<10}")
            print("-" * 30)
            for status_item in status_list:
                print(f"{status_item['sensor_id']:<15} | {status_item['status']:<10}")
            print()
 
            if update_status_in_db(status_list):
                print(f"âœ… Status saved at {current_time} (issync=0)")
                print(f"   ðŸ“ Inserted {len(status_list)} status records")
            print()
 
        time.sleep(LOG_INTERVAL)
 
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nðŸ›‘ Logger stopped.")