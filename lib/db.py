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