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