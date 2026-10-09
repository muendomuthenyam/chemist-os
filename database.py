import os
import sqlite3
from dotenv import load_dotenv
import security

load_dotenv()

DB_PATH = os.getenv("SQLITE_DB_PATH", "chemist_app.db")

def get_db_connection():
    """Establishes thread-safe SQLite connection with dict-like row access."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes schema and runs automatic safe migrations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table (Owner & Attendants)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            pin_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Tenants Table (Includes owner_email for verification)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            owner_phone TEXT UNIQUE NOT NULL,
            owner_email TEXT UNIQUE,
            pin_code_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            subscription_status TEXT DEFAULT 'trial',
            last_payment_date DATETIME
        )
    ''')

    # Safe Schema Migration Check: Ensure 'owner_email' column exists if table was created previously
    cursor.execute("PRAGMA table_info(tenants)")
    tenant_columns = [col[1] for col in cursor.fetchall()]
    if "owner_email" not in tenant_columns:
        cursor.execute("ALTER TABLE tenants ADD COLUMN owner_email TEXT")

    # 3. Inventory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_name TEXT NOT NULL,
            generic_name TEXT,
            category TEXT DEFAULT 'OTC',
            batch_number TEXT NOT NULL,
            expiry_date DATE NOT NULL,
            vat_category TEXT DEFAULT 'EXEMPT',
            units_per_box INTEGER DEFAULT 1,
            tablets_per_unit INTEGER DEFAULT 1,
            stock_qty_units INTEGER NOT NULL,
            buying_price_box REAL NOT NULL,
            selling_price_unit REAL NOT NULL,
            selling_price_tablet REAL,
            min_reorder_level INTEGER DEFAULT 5,
            is_quarantined INTEGER DEFAULT 0
        )
    ''')

    # 4. Sales Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cashier_name TEXT DEFAULT 'Attendant',
            payment_mode TEXT NOT NULL,
            total_amount REAL NOT NULL,
            vat_amount REAL DEFAULT 0.0,
            mpesa_ref TEXT
        )
    ''')

    # 5. Sale Items Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            inventory_id INTEGER,
            unit_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            profit_generated REAL NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales (id),
            FOREIGN KEY (inventory_id) REFERENCES inventory (id)
        )
    ''')

    # 6. POM Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pom_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            prescriber_doctor TEXT NOT NULL,
            license_ref TEXT,
            patient_name TEXT,
            FOREIGN KEY (sale_id) REFERENCES sales (id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database Schema Initialized & Verified.")