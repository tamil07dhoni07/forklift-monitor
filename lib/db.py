# ================================================================
#  db.py  —  Gear IQ  Database connection (shared)
# ================================================================
import psycopg2

DB_CONFIG = {
    'host':     'localhost',
    'port':     5432,
    'dbname':   'gearid_db',
    'user':     'postgres',
    'password': 'root'
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f'[DB] Connection failed → {e}')
        return None
    
def delete_old_voltage_records():
    """Keep only today's records in voltage_data. Delete everything older."""
    conn = get_db_connection()
    if not conn:
        print('[DB] delete_old_voltage_records → no connection')
        return

    try:
        cur = conn.cursor()

        # Count before delete
        cur.execute("""
            SELECT COUNT(*) FROM voltage_data
            WHERE timestamp < CURRENT_DATE
        """)
        old_count = cur.fetchone()[0]

        if old_count == 0:
            print('[DB] delete_old_voltage_records → nothing to delete')
            cur.close()
            conn.close()
            return

        # Delete old records
        cur.execute("""
            DELETE FROM voltage_data
            WHERE timestamp < CURRENT_DATE
        """)

        conn.commit()
        cur.close()
        print(f'[DB] delete_old_voltage_records → deleted {old_count} old record(s) ✅')

    except Exception as e:
        conn.rollback()
        print(f'[DB] delete_old_voltage_records ERROR → {e}')
    finally:
        conn.close()


def delete_old_vibration_records():
    """Keep only today's records in vibration_sensor_data."""
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM vibration_sensor_data WHERE timestamp < CURRENT_DATE")
        old_count = cur.fetchone()[0]
        cur.execute("DELETE FROM vibration_sensor_data WHERE timestamp < CURRENT_DATE")
        conn.commit()
        cur.close()
        print(f'[DB] delete_old_vibration_records → deleted {old_count} record(s) ✅')
    except Exception as e:
        conn.rollback()
        print(f'[DB] delete_old_vibration_records ERROR → {e}')
    finally:
        conn.close()

def delete_old_temperature_records():
    """Keep only today's records in temperature_data."""
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM temperature_data WHERE timestamp < CURRENT_DATE")
        old_count = cur.fetchone()[0]
        cur.execute("DELETE FROM temperature_data WHERE timestamp < CURRENT_DATE")
        conn.commit()
        cur.close()
        print(f'[DB] delete_old_temperature_records → deleted {old_count} record(s) ✅')
    except Exception as e:
        conn.rollback()
        print(f'[DB] delete_old_temperature_records ERROR → {e}')
    finally:
        conn.close()

def delete_old_oil_records():
    """Keep only today's records in fuel_level_sensor_data."""
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fuel_level_sensor_data WHERE timestamp < CURRENT_DATE")
        old_count = cur.fetchone()[0]
        cur.execute("DELETE FROM fuel_level_sensor_data WHERE timestamp < CURRENT_DATE")
        conn.commit()
        cur.close()
        print(f'[DB] delete_old_oil_records → deleted {old_count} record(s) ✅')
    except Exception as e:
        conn.rollback()
        print(f'[DB] delete_old_oil_records ERROR → {e}')
    finally:
        conn.close()

def delete_old_alert_records():
    """Keep only today's records in alert_data."""
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM alerts WHERE timestamp < CURRENT_DATE")
        old_count = cur.fetchone()[0]
        cur.execute("DELETE FROM alerts WHERE timestamp < CURRENT_DATE")
        conn.commit()
        cur.close()
        print(f'[DB] delete_old_alert_records → deleted {old_count} record(s) ✅')
    except Exception as e:
        conn.rollback()
        print(f'[DB] delete_old_alert_records ERROR → {e}')
    finally:
        conn.close()

def delete_old_current_sensor_records():
    """Keep only today's records in current_sensor_data."""
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM current_sensor_data WHERE timestamp < CURRENT_DATE")
        old_count = cur.fetchone()[0]
        cur.execute("DELETE FROM current_sensor_data WHERE timestamp < CURRENT_DATE")
        conn.commit()
        cur.close()
        print(f'[DB] delete_old_current_sensor_records → deleted {old_count} record(s) ✅')
    except Exception as e:
        conn.rollback()
        print(f'[DB] delete_old_current_sensor_records ERROR → {e}')
    finally:
        conn.close()

def delete_old_status_details_records():
    """Keep only today's records in status_details."""
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM status_details WHERE timestamp < CURRENT_DATE")
        old_count = cur.fetchone()[0]
        cur.execute("DELETE FROM status_details WHERE timestamp < CURRENT_DATE")
        conn.commit()
        cur.close()
        print(f'[DB] delete_old_status_details_records → deleted {old_count} record(s) ✅')
    except Exception as e:
        conn.rollback()
        print(f'[DB] delete_old_status_details_records ERROR → {e}')
    finally:
        conn.close()