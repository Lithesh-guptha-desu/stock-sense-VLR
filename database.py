import sqlite3
import hashlib
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stocksense.db")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Inventory Manager',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # OTPs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        expires_at DATETIME NOT NULL,
        verified INTEGER DEFAULT 0
    )
    ''')

    # Categories Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT
    )
    ''')

    # Warehouses Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        address TEXT,
        status TEXT DEFAULT 'Active'
    )
    ''')

    # Locations Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        warehouse_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE CASCADE
    )
    ''')

    # Products Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sku TEXT UNIQUE NOT NULL,
        category_id INTEGER NOT NULL,
        unit_of_measure TEXT NOT NULL DEFAULT 'Units',
        reorder_level INTEGER NOT NULL DEFAULT 10,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    ''')

    # Stock Table (Single source of truth stock quantity per location)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, location_id),
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
        FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE CASCADE
    )
    ''')

    # Receipts Table (Incoming Goods)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT UNIQUE NOT NULL,
        supplier TEXT NOT NULL,
        warehouse_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT', -- DRAFT, WAITING, READY, DONE, CANCELED
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        validated_at DATETIME,
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
        FOREIGN KEY (created_by) REFERENCES users (id)
    )
    ''')

    # Receipt Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS receipt_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (receipt_id) REFERENCES receipts (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (location_id) REFERENCES locations (id)
    )
    ''')

    # Deliveries Table (Outgoing Goods)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT UNIQUE NOT NULL,
        customer TEXT NOT NULL,
        warehouse_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT', -- DRAFT, WAITING, READY, DONE, CANCELED
        picking_status TEXT DEFAULT 'Pending',
        packing_status TEXT DEFAULT 'Pending',
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        validated_at DATETIME,
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
        FOREIGN KEY (created_by) REFERENCES users (id)
    )
    ''')

    # Delivery Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS delivery_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        delivery_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (delivery_id) REFERENCES deliveries (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (location_id) REFERENCES locations (id)
    )
    ''')

    # Transfers Table (Internal Stock Movements)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT UNIQUE NOT NULL,
        source_location_id INTEGER NOT NULL,
        destination_location_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT', -- DRAFT, WAITING, READY, DONE, CANCELED
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME,
        FOREIGN KEY (source_location_id) REFERENCES locations (id),
        FOREIGN KEY (destination_location_id) REFERENCES locations (id),
        FOREIGN KEY (created_by) REFERENCES users (id)
    )
    ''')

    # Transfer Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transfer_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (transfer_id) REFERENCES transfers (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')

    # Adjustments Table (Physical Stock Adjustments)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT UNIQUE NOT NULL,
        product_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        system_quantity INTEGER NOT NULL,
        physical_quantity INTEGER NOT NULL,
        difference INTEGER NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'DONE',
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (location_id) REFERENCES locations (id),
        FOREIGN KEY (created_by) REFERENCES users (id)
    )
    ''')

    # Stock Ledger Table (Audit Log of ALL Movements)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        product_id INTEGER NOT NULL,
        sku TEXT NOT NULL,
        operation_type TEXT NOT NULL, -- RECEIPT, DELIVERY, INTERNAL TRANSFER, ADJUSTMENT
        reference_id TEXT NOT NULL,
        source_location_id INTEGER,
        destination_location_id INTEGER,
        quantity INTEGER NOT NULL,
        previous_quantity INTEGER NOT NULL,
        new_quantity INTEGER NOT NULL,
        user_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (source_location_id) REFERENCES locations (id),
        FOREIGN KEY (destination_location_id) REFERENCES locations (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    conn.commit()
    conn.close()
    print("Database tables initialized successfully.")

def seed_data():
    conn = get_db()
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("Seeding initial data...")

    # Seed Users
    default_pass = hash_password("admin123")
    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("Alex Mercer", "alex@stocksense.io", default_pass, "Inventory Manager"))
    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("Sam Jenkins", "sam@stocksense.io", default_pass, "Warehouse Staff"))
    user_id = 1

    # Seed Categories
    categories = [
        ("Raw Materials", "Primary materials used in production"),
        ("Finished Goods", "Completed items ready for sale & shipment"),
        ("Components", "Parts and sub-assemblies"),
        ("Tools", "Operational machinery and tools"),
        ("Electrical", "Wires, circuits, and electronic modules")
    ]
    for name, desc in categories:
        cursor.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (name, desc))

    # Seed Warehouses
    cursor.execute("INSERT INTO warehouses (name, code, address, status) VALUES (?, ?, ?, ?)",
                   ("Main Distribution Center", "WH-01", "100 Logistics Blvd, Industrial Zone", "Active"))
    cursor.execute("INSERT INTO warehouses (name, code, address, status) VALUES (?, ?, ?, ?)",
                   ("Production Hub & Storage", "WH-02", "45 Manufacturing Way, Tech Park", "Active"))

    # Seed Locations
    locations = [
        (1, "Main Store", "WH-01-MAIN"),
        (1, "Rack A", "WH-01-RACK-A"),
        (1, "Rack B", "WH-01-RACK-B"),
        (2, "Production Floor", "WH-02-PROD"),
        (2, "Storage Zone C", "WH-02-ZONE-C")
    ]
    for wh_id, name, code in locations:
        cursor.execute("INSERT INTO locations (warehouse_id, name, code) VALUES (?, ?, ?)", (wh_id, name, code))

    # Seed Products
    products = [
        ("Steel Rods 12mm", "SKU-STL-001", 1, "Meters", 50),
        ("Copper Wire 2.5mm", "SKU-CPR-002", 1, "Meters", 30),
        ("Ergonomic Mesh Chair", "SKU-CHR-101", 2, "Units", 15),
        ("Heavy Duty Bolts M8", "SKU-BLT-501", 3, "Boxes", 100),
        ("Precision Caliper Tool", "SKU-TOL-901", 4, "Units", 5),
        ("Aluminum Ingot 5kg", "SKU-ALU-003", 1, "Kg", 20),
        ("LED Control Circuit Board", "SKU-CIR-202", 5, "Units", 25)
    ]
    for name, sku, cat_id, uom, reorder in products:
        cursor.execute("INSERT INTO products (name, sku, category_id, unit_of_measure, reorder_level) VALUES (?, ?, ?, ?, ?)",
                       (name, sku, cat_id, uom, reorder))

    # Seed Stock (Initial balance)
    initial_stocks = [
        (1, 1, 45),  # Steel Rods in Main Store (45 < 50 reorder -> Low Stock)
        (2, 2, 8),   # Copper Wire in Rack A (8 < 30 reorder -> Low Stock)
        (3, 1, 42),  # Ergonomic Chair in Main Store
        (4, 3, 350), # Bolts in Rack B
        (5, 4, 2),   # Caliper in Production Floor (2 < 5 reorder -> Low Stock)
        (6, 1, 65),  # Aluminum in Main Store
        (7, 5, 0)    # LED Circuit Board in Zone C (0 -> Out of Stock)
    ]
    for prod_id, loc_id, qty in initial_stocks:
        cursor.execute("INSERT INTO stock (product_id, location_id, quantity) VALUES (?, ?, ?)", (prod_id, loc_id, qty))

    # Seed Initial Stock Ledger Entries for initial stock
    ledger_entries = [
        (1, "SKU-STL-001", "RECEIPT", "REC-1000", None, 1, 45, 0, 45, user_id),
        (2, "SKU-CPR-002", "RECEIPT", "REC-1000", None, 2, 8, 0, 8, user_id),
        (3, "SKU-CHR-101", "RECEIPT", "REC-1001", None, 1, 42, 0, 42, user_id),
        (4, "SKU-BLT-501", "RECEIPT", "REC-1001", None, 3, 350, 0, 350, user_id),
        (5, "SKU-TOL-901", "RECEIPT", "REC-1002", None, 4, 2, 0, 2, user_id),
        (6, "SKU-ALU-003", "RECEIPT", "REC-1002", None, 1, 65, 0, 65, user_id),
    ]
    for prod_id, sku, op, ref, src, dst, qty, prev_q, new_q, usr in ledger_entries:
        cursor.execute('''
        INSERT INTO stock_ledger (product_id, sku, operation_type, reference_id, source_location_id, destination_location_id, quantity, previous_quantity, new_quantity, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (prod_id, sku, op, ref, src, dst, qty, prev_q, new_q, usr))

    # Seed Sample Operations (Pending & Completed)
    # 1. Receipt DONE
    cursor.execute("INSERT INTO receipts (reference_number, supplier, warehouse_id, status, created_by, validated_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                   ("REC-1000", "Apex Metals Inc.", 1, "DONE", user_id))
    rec_id = cursor.lastrowid
    cursor.execute("INSERT INTO receipt_items (receipt_id, product_id, location_id, quantity) VALUES (?, ?, ?, ?)", (rec_id, 1, 1, 45))

    # 2. Receipt WAITING / PENDING
    cursor.execute("INSERT INTO receipts (reference_number, supplier, warehouse_id, status, created_by) VALUES (?, ?, ?, ?, ?)",
                   ("REC-1024", "Global Dynamics Ltd", 1, "WAITING", user_id))
    rec_id2 = cursor.lastrowid
    cursor.execute("INSERT INTO receipt_items (receipt_id, product_id, location_id, quantity) VALUES (?, ?, ?, ?)", (rec_id2, 1, 1, 100))
    cursor.execute("INSERT INTO receipt_items (receipt_id, product_id, location_id, quantity) VALUES (?, ?, ?, ?)", (rec_id2, 2, 2, 50))

    # 3. Delivery Order DONE
    cursor.execute("INSERT INTO deliveries (reference_number, customer, warehouse_id, status, picking_status, packing_status, created_by, validated_at) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                   ("DEL-1040", "Horizon Office Solutions", 1, "DONE", "Picked", "Packed", user_id))
    del_id = cursor.lastrowid
    cursor.execute("INSERT INTO delivery_items (delivery_id, product_id, location_id, quantity) VALUES (?, ?, ?, ?)", (del_id, 3, 1, 10))

    # 4. Delivery Order READY / PENDING
    cursor.execute("INSERT INTO deliveries (reference_number, customer, warehouse_id, status, picking_status, packing_status, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ("DEL-1042", "Vanguard Industries", 1, "READY", "Picked", "In Packing", user_id))
    del_id2 = cursor.lastrowid
    cursor.execute("INSERT INTO delivery_items (delivery_id, product_id, location_id, quantity) VALUES (?, ?, ?, ?)", (del_id2, 3, 1, 5))

    # 5. Internal Transfer READY
    cursor.execute("INSERT INTO transfers (reference_number, source_location_id, destination_location_id, status, created_by) VALUES (?, ?, ?, ?, ?)",
                   ("TRF-1003", 1, 4, "READY", user_id))
    trf_id = cursor.lastrowid
    cursor.execute("INSERT INTO transfer_items (transfer_id, product_id, quantity) VALUES (?, ?, ?)", (trf_id, 1, 20))

    # 6. Adjustment DONE
    cursor.execute("INSERT INTO adjustments (reference_number, product_id, location_id, system_quantity, physical_quantity, difference, reason, status, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   ("ADJ-5001", 1, 1, 48, 45, -3, "Routine Audit Discrepancy", "DONE", user_id))
    cursor.execute('''
    INSERT INTO stock_ledger (product_id, sku, operation_type, reference_id, source_location_id, destination_location_id, quantity, previous_quantity, new_quantity, user_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (1, "SKU-STL-001", "ADJUSTMENT", "ADJ-5001", 1, 1, -3, 48, 45, user_id))

    conn.commit()
    conn.close()
    print("Database seeded successfully.")

if __name__ == '__main__':
    init_db()
    seed_data()
