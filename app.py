import os
import random
import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from database import get_db, init_db, seed_data, hash_password
from stock_engine import StockEngine, StockEngineError

app = Flask(__name__, static_folder="../static", static_url_path="")
CORS(app)

# Ensure database is initialized and seeded on app startup
init_db()
seed_data()

# Helper function to convert SQLite Row objects to dicts
def row_to_dict(row):
    return dict(row) if row else None

# Serve Frontend HTML
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# ----------------------------------------------------
# AUTHENTICATION APIS
# ----------------------------------------------------
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    confirm_password = data.get("confirmPassword") or data.get("confirm_password")

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Email address already registered."}), 400

    pass_hash = hash_password(password)
    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'Inventory Manager')",
                   (name, email, pass_hash))
    conn.commit()
    user_id = cursor.lastrowid
    cursor.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,))
    user = row_to_dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": "Account created successfully.",
        "user": user,
        "token": f"mock-jwt-token-{user_id}"
    }), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    pass_hash = hash_password(password)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, password_hash FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user or user["password_hash"] != pass_hash:
        conn.close()
        return jsonify({"error": "Invalid email or password."}), 401

    user_dict = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"]
    }
    conn.close()

    return jsonify({
        "message": "Login successful.",
        "user": user_dict,
        "token": f"mock-jwt-token-{user['id']}"
    }), 200

@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.json or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "No user account found with that email address."}), 404

    # Generate 6-digit OTP code
    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.datetime.now() + datetime.timedelta(minutes=15)

    cursor.execute("INSERT INTO otps (email, code, expires_at) VALUES (?, ?, ?)",
                   (email, otp_code, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    return jsonify({
        "message": f"OTP sent to {email}.",
        "otp_debug": otp_code  # Returned for ease of demonstration/testing
    }), 200

@app.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json or {}
    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        return jsonify({"error": "Email and OTP code are required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM otps WHERE email = ? AND code = ? AND verified = 0 ORDER BY id DESC LIMIT 1", (email, code))
    otp_row = cursor.fetchone()

    if not otp_row:
        conn.close()
        return jsonify({"error": "Invalid or expired OTP code."}), 400

    cursor.execute("UPDATE otps SET verified = 1 WHERE id = ?", (otp_row["id"],))
    conn.commit()
    conn.close()

    return jsonify({"message": "OTP verified successfully."}), 200

@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.json or {}
    email = data.get("email")
    code = data.get("code")
    new_password = data.get("newPassword") or data.get("new_password")

    if not email or not code or not new_password:
        return jsonify({"error": "Email, OTP, and new password are required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM otps WHERE email = ? AND code = ? AND verified = 1 ORDER BY id DESC LIMIT 1", (email, code))
    otp_row = cursor.fetchone()

    if not otp_row:
        conn.close()
        return jsonify({"error": "OTP verification incomplete or code expired."}), 400

    new_hash = hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (new_hash, email))
    conn.commit()
    conn.close()

    return jsonify({"message": "Password updated successfully. You can now login."}), 200

# ----------------------------------------------------
# PRODUCT MANAGEMENT APIS
# ----------------------------------------------------
@app.route("/api/products", methods=["GET"])
def get_products():
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id")
    warehouse_id = request.args.get("warehouse_id")
    location_id = request.args.get("location_id")
    stock_status = request.args.get("stock_status")

    conn = get_db()
    cursor = conn.cursor()

    query = '''
    SELECT p.*, c.name as category_name,
           COALESCE(SUM(s.quantity), 0) as total_stock
    FROM products p
    JOIN categories c ON p.category_id = c.id
    LEFT JOIN stock s ON p.id = s.product_id
    LEFT JOIN locations l ON s.location_id = l.id
    WHERE 1=1
    '''
    params = []

    if search:
        query += " AND (p.name LIKE ? OR p.sku LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if category_id:
        query += " AND p.category_id = ?"
        params.append(category_id)

    if warehouse_id:
        query += " AND l.warehouse_id = ?"
        params.append(warehouse_id)

    if location_id:
        query += " AND s.location_id = ?"
        params.append(location_id)

    query += " GROUP BY p.id ORDER BY p.name ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    products = []
    for r in rows:
        p_dict = row_to_dict(r)
        total = p_dict["total_stock"]
        reorder = p_dict["reorder_level"]

        if total == 0:
            status = "Out of Stock"
        elif total <= reorder:
            status = "Low Stock"
        else:
            status = "In Stock"

        p_dict["stock_status"] = status

        # Fetch location details for product
        cursor.execute('''
        SELECT s.quantity, l.name as location_name, l.code as location_code, w.name as warehouse_name
        FROM stock s
        JOIN locations l ON s.location_id = l.id
        JOIN warehouses w ON l.warehouse_id = w.id
        WHERE s.product_id = ?
        ''', (p_dict["id"],))
        p_dict["locations"] = [row_to_dict(loc) for loc in cursor.fetchall()]

        # Filter by stock_status if specified
        if not stock_status or stock_status == "All" or status == stock_status:
            products.append(p_dict)

    conn.close()
    return jsonify(products), 200

@app.route("/api/products", methods=["POST"])
def create_product():
    data = request.json or {}
    name = data.get("name")
    sku = data.get("sku")
    category_id = data.get("category_id")
    unit_of_measure = data.get("unit_of_measure", "Units")
    reorder_level = int(data.get("reorder_level", 10))
    initial_stock = int(data.get("initial_stock", 0))
    location_id = data.get("location_id")

    if not name or not sku or not category_id:
        return jsonify({"error": "Product Name, SKU, and Category are required."}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO products (name, sku, category_id, unit_of_measure, reorder_level) VALUES (?, ?, ?, ?, ?)",
                       (name, sku, category_id, unit_of_measure, reorder_level))
        prod_id = cursor.lastrowid

        if initial_stock > 0 and location_id:
            cursor.execute("INSERT INTO stock (product_id, location_id, quantity) VALUES (?, ?, ?)",
                           (prod_id, location_id, initial_stock))
            # Log initial stock in stock_ledger
            cursor.execute('''
            INSERT INTO stock_ledger (product_id, sku, operation_type, reference_id, source_location_id, destination_location_id, quantity, previous_quantity, new_quantity, user_id)
            VALUES (?, ?, 'RECEIPT', 'INITIAL-STOCK', NULL, ?, ?, 0, ?, 1)
            ''', (prod_id, sku, location_id, initial_stock, initial_stock))

        conn.commit()

        cursor.execute("SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?", (prod_id,))
        new_prod = row_to_dict(cursor.fetchone())
        conn.close()

        return jsonify({"message": "Product created successfully.", "product": new_prod}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"Product with SKU '{sku}' already exists."}), 400

@app.route("/api/products/<int:prod_id>", methods=["GET"])
def get_product_detail(prod_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT p.*, c.name as category_name, COALESCE(SUM(s.quantity), 0) as total_stock
    FROM products p
    JOIN categories c ON p.category_id = c.id
    LEFT JOIN stock s ON p.id = s.product_id
    WHERE p.id = ?
    GROUP BY p.id
    ''', (prod_id,))
    product = row_to_dict(cursor.fetchone())

    if not product:
        conn.close()
        return jsonify({"error": "Product not found."}), 404

    # Stock by location
    cursor.execute('''
    SELECT s.quantity, l.id as location_id, l.name as location_name, l.code as location_code, w.name as warehouse_name
    FROM stock s
    JOIN locations l ON s.location_id = l.id
    JOIN warehouses w ON l.warehouse_id = w.id
    WHERE s.product_id = ?
    ''', (prod_id,))
    product["locations"] = [row_to_dict(r) for r in cursor.fetchall()]

    # Product stock ledger history
    cursor.execute('''
    SELECT sl.*, u.name as user_name,
           l1.name as source_location_name,
           l2.name as destination_location_name
    FROM stock_ledger sl
    LEFT JOIN users u ON sl.user_id = u.id
    LEFT JOIN locations l1 ON sl.source_location_id = l1.id
    LEFT JOIN locations l2 ON sl.destination_location_id = l2.id
    WHERE sl.product_id = ?
    ORDER BY sl.id DESC
    ''', (prod_id,))
    product["ledger_history"] = [row_to_dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(product), 200

@app.route("/api/products/<int:prod_id>", methods=["PUT"])
def update_product(prod_id):
    data = request.json or {}
    conn = get_db()
    cursor = conn.cursor()

    name = data.get("name")
    sku = data.get("sku")
    category_id = data.get("category_id")
    unit_of_measure = data.get("unit_of_measure")
    reorder_level = data.get("reorder_level")

    cursor.execute("UPDATE products SET name = ?, sku = ?, category_id = ?, unit_of_measure = ?, reorder_level = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (name, sku, category_id, unit_of_measure, reorder_level, prod_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product updated successfully."}), 200

@app.route("/api/products/<int:prod_id>", methods=["DELETE"])
def delete_product(prod_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product deleted successfully."}), 200

# ----------------------------------------------------
# WAREHOUSES & LOCATIONS APIS
# ----------------------------------------------------
@app.route("/api/warehouses", methods=["GET"])
def get_warehouses():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM warehouses ORDER BY name ASC")
    warehouses = [row_to_dict(r) for r in cursor.fetchall()]

    for wh in warehouses:
        cursor.execute("SELECT * FROM locations WHERE warehouse_id = ? ORDER BY name ASC", (wh["id"],))
        wh["locations"] = [row_to_dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(warehouses), 200

@app.route("/api/warehouses", methods=["POST"])
def create_warehouse():
    data = request.json or {}
    name = data.get("name")
    code = data.get("code")
    address = data.get("address")

    if not name or not code:
        return jsonify({"error": "Warehouse name and code are required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO warehouses (name, code, address) VALUES (?, ?, ?)", (name, code, address))
        wh_id = cursor.lastrowid
        # Create default location for warehouse
        cursor.execute("INSERT INTO locations (warehouse_id, name, code) VALUES (?, 'Main Rack', ?)",
                       (wh_id, f"{code}-MAIN"))
        conn.commit()
        conn.close()
        return jsonify({"message": "Warehouse created successfully."}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Warehouse code already exists."}), 400

@app.route("/api/locations", methods=["GET"])
def get_locations():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT l.*, w.name as warehouse_name, w.code as warehouse_code
    FROM locations l
    JOIN warehouses w ON l.warehouse_id = w.id
    ORDER BY w.name, l.name
    ''')
    locations = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(locations), 200

@app.route("/api/categories", methods=["GET"])
def get_categories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name ASC")
    categories = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(categories), 200

# ----------------------------------------------------
# RECEIPTS APIS (INCOMING GOODS)
# ----------------------------------------------------
@app.route("/api/receipts", methods=["GET"])
def get_receipts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT r.*, w.name as warehouse_name, u.name as created_by_name,
           COUNT(ri.id) as item_count, COALESCE(SUM(ri.quantity), 0) as total_quantity
    FROM receipts r
    JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN users u ON r.created_by = u.id
    LEFT JOIN receipt_items ri ON r.id = ri.receipt_id
    GROUP BY r.id
    ORDER BY r.id DESC
    ''')
    receipts = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(receipts), 200

@app.route("/api/receipts/<int:rec_id>", methods=["GET"])
def get_receipt_detail(rec_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT r.*, w.name as warehouse_name, u.name as created_by_name
    FROM receipts r
    JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN users u ON r.created_by = u.id
    WHERE r.id = ?
    ''', (rec_id,))
    receipt = row_to_dict(cursor.fetchone())

    if not receipt:
        conn.close()
        return jsonify({"error": "Receipt not found."}), 404

    cursor.execute('''
    SELECT ri.*, p.name as product_name, p.sku, p.unit_of_measure, l.name as location_name, l.code as location_code
    FROM receipt_items ri
    JOIN products p ON ri.product_id = p.id
    JOIN locations l ON ri.location_id = l.id
    WHERE ri.receipt_id = ?
    ''', (rec_id,))
    receipt["items"] = [row_to_dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(receipt), 200

@app.route("/api/receipts", methods=["POST"])
def create_receipt():
    data = request.json or {}
    supplier = data.get("supplier")
    warehouse_id = data.get("warehouse_id")
    items = data.get("items", []) # [{product_id, location_id, quantity}]

    if not supplier or not warehouse_id or not items:
        return jsonify({"error": "Supplier, Warehouse, and Product items are required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM receipts")
    count = cursor.fetchone()[0] + 1
    ref_no = f"REC-{1020 + count}"

    cursor.execute("INSERT INTO receipts (reference_number, supplier, warehouse_id, status, created_by) VALUES (?, ?, ?, 'WAITING', 1)",
                   (ref_no, supplier, warehouse_id))
    rec_id = cursor.lastrowid

    for item in items:
        cursor.execute("INSERT INTO receipt_items (receipt_id, product_id, location_id, quantity) VALUES (?, ?, ?, ?)",
                       (rec_id, item["product_id"], item["location_id"], int(item["quantity"])))

    conn.commit()
    conn.close()
    return jsonify({"message": f"Receipt {ref_no} created in WAITING status.", "id": rec_id, "reference_number": ref_no}), 201

@app.route("/api/receipts/<int:rec_id>/validate", methods=["POST"])
def validate_receipt_endpoint(rec_id):
    try:
        StockEngine.validate_receipt(rec_id, user_id=1)
        return jsonify({"message": f"Receipt #{rec_id} validated successfully. Stock updated and logged to ledger."}), 200
    except StockEngineError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Server error during receipt validation."}), 500

@app.route("/api/receipts/<int:rec_id>/cancel", methods=["POST"])
def cancel_receipt(rec_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE receipts SET status = 'CANCELED' WHERE id = ? AND status != 'DONE'", (rec_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Receipt canceled."}), 200

# ----------------------------------------------------
# DELIVERIES APIS (OUTGOING GOODS)
# ----------------------------------------------------
@app.route("/api/deliveries", methods=["GET"])
def get_deliveries():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT d.*, w.name as warehouse_name, u.name as created_by_name,
           COUNT(di.id) as item_count, COALESCE(SUM(di.quantity), 0) as total_quantity
    FROM deliveries d
    JOIN warehouses w ON d.warehouse_id = w.id
    LEFT JOIN users u ON d.created_by = u.id
    LEFT JOIN delivery_items di ON d.id = di.delivery_id
    GROUP BY d.id
    ORDER BY d.id DESC
    ''')
    deliveries = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(deliveries), 200

@app.route("/api/deliveries/<int:del_id>", methods=["GET"])
def get_delivery_detail(del_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT d.*, w.name as warehouse_name, u.name as created_by_name
    FROM deliveries d
    JOIN warehouses w ON d.warehouse_id = w.id
    LEFT JOIN users u ON d.created_by = u.id
    WHERE d.id = ?
    ''', (del_id,))
    delivery = row_to_dict(cursor.fetchone())

    if not delivery:
        conn.close()
        return jsonify({"error": "Delivery order not found."}), 404

    cursor.execute('''
    SELECT di.*, p.name as product_name, p.sku, p.unit_of_measure, l.name as location_name, l.code as location_code
    FROM delivery_items di
    JOIN products p ON di.product_id = p.id
    JOIN locations l ON di.location_id = l.id
    WHERE di.delivery_id = ?
    ''', (del_id,))
    delivery["items"] = [row_to_dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(delivery), 200

@app.route("/api/deliveries", methods=["POST"])
def create_delivery():
    data = request.json or {}
    customer = data.get("customer")
    warehouse_id = data.get("warehouse_id")
    items = data.get("items", [])

    if not customer or not warehouse_id or not items:
        return jsonify({"error": "Customer, Warehouse, and Product items are required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM deliveries")
    count = cursor.fetchone()[0] + 1
    ref_no = f"DEL-{1040 + count}"

    cursor.execute("INSERT INTO deliveries (reference_number, customer, warehouse_id, status, picking_status, packing_status, created_by) VALUES (?, ?, ?, 'READY', 'Picked', 'Packed', 1)",
                   (ref_no, customer, warehouse_id))
    del_id = cursor.lastrowid

    for item in items:
        cursor.execute("INSERT INTO delivery_items (delivery_id, product_id, location_id, quantity) VALUES (?, ?, ?, ?)",
                       (del_id, item["product_id"], item["location_id"], int(item["quantity"])))

    conn.commit()
    conn.close()
    return jsonify({"message": f"Delivery Order {ref_no} created.", "id": del_id, "reference_number": ref_no}), 201

@app.route("/api/deliveries/<int:del_id>/validate", methods=["POST"])
def validate_delivery_endpoint(del_id):
    try:
        StockEngine.validate_delivery(del_id, user_id=1)
        return jsonify({"message": f"Delivery Order #{del_id} validated. Stock deducted and logged to ledger."}), 200
    except StockEngineError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Server error during delivery validation."}), 500

@app.route("/api/deliveries/<int:del_id>/cancel", methods=["POST"])
def cancel_delivery(del_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE deliveries SET status = 'CANCELED' WHERE id = ? AND status != 'DONE'", (del_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Delivery order canceled."}), 200

# ----------------------------------------------------
# TRANSFERS APIS (INTERNAL MOVEMENTS)
# ----------------------------------------------------
@app.route("/api/transfers", methods=["GET"])
def get_transfers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT t.*, l1.name as source_location_name, l1.code as source_code,
           l2.name as destination_location_name, l2.code as destination_code,
           u.name as created_by_name,
           COUNT(ti.id) as item_count, COALESCE(SUM(ti.quantity), 0) as total_quantity
    FROM transfers t
    JOIN locations l1 ON t.source_location_id = l1.id
    JOIN locations l2 ON t.destination_location_id = l2.id
    LEFT JOIN users u ON t.created_by = u.id
    LEFT JOIN transfer_items ti ON t.id = ti.transfer_id
    GROUP BY t.id
    ORDER BY t.id DESC
    ''')
    transfers = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(transfers), 200

@app.route("/api/transfers/<int:trf_id>", methods=["GET"])
def get_transfer_detail(trf_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT t.*, l1.name as source_location_name, l1.code as source_code,
           l2.name as destination_location_name, l2.code as destination_code,
           u.name as created_by_name
    FROM transfers t
    JOIN locations l1 ON t.source_location_id = l1.id
    JOIN locations l2 ON t.destination_location_id = l2.id
    LEFT JOIN users u ON t.created_by = u.id
    WHERE t.id = ?
    ''', (trf_id,))
    transfer = row_to_dict(cursor.fetchone())

    if not transfer:
        conn.close()
        return jsonify({"error": "Transfer not found."}), 404

    cursor.execute('''
    SELECT ti.*, p.name as product_name, p.sku, p.unit_of_measure
    FROM transfer_items ti
    JOIN products p ON ti.product_id = p.id
    WHERE ti.transfer_id = ?
    ''', (trf_id,))
    transfer["items"] = [row_to_dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(transfer), 200

@app.route("/api/transfers", methods=["POST"])
def create_transfer():
    data = request.json or {}
    source_location_id = data.get("source_location_id")
    destination_location_id = data.get("destination_location_id")
    items = data.get("items", [])

    if not source_location_id or not destination_location_id or not items:
        return jsonify({"error": "Source location, Destination location, and Products are required."}), 400

    if int(source_location_id) == int(destination_location_id):
        return jsonify({"error": "Source and Destination locations must be different."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transfers")
    count = cursor.fetchone()[0] + 1
    ref_no = f"TRF-{1000 + count}"

    cursor.execute("INSERT INTO transfers (reference_number, source_location_id, destination_location_id, status, created_by) VALUES (?, ?, ?, 'READY', 1)",
                   (ref_no, source_location_id, destination_location_id))
    trf_id = cursor.lastrowid

    for item in items:
        cursor.execute("INSERT INTO transfer_items (transfer_id, product_id, quantity) VALUES (?, ?, ?)",
                       (trf_id, item["product_id"], int(item["quantity"])))

    conn.commit()
    conn.close()
    return jsonify({"message": f"Transfer {ref_no} created.", "id": trf_id, "reference_number": ref_no}), 201

@app.route("/api/transfers/<int:trf_id>/validate", methods=["POST"])
def validate_transfer_endpoint(trf_id):
    try:
        StockEngine.validate_transfer(trf_id, user_id=1)
        return jsonify({"message": f"Transfer Order #{trf_id} completed. Stock moved and logged to ledger."}), 200
    except StockEngineError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Server error during transfer validation."}), 500

@app.route("/api/transfers/<int:trf_id>/cancel", methods=["POST"])
def cancel_transfer(trf_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE transfers SET status = 'CANCELED' WHERE id = ? AND status != 'DONE'", (trf_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Transfer canceled."}), 200

# ----------------------------------------------------
# ADJUSTMENTS APIS (PHYSICAL STOCK COUNT)
# ----------------------------------------------------
@app.route("/api/adjustments", methods=["GET"])
def get_adjustments():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT a.*, p.name as product_name, p.sku, p.unit_of_measure,
           l.name as location_name, l.code as location_code,
           u.name as created_by_name
    FROM adjustments a
    JOIN products p ON a.product_id = p.id
    JOIN locations l ON a.location_id = l.id
    LEFT JOIN users u ON a.created_by = u.id
    ORDER BY a.id DESC
    ''')
    adjustments = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(adjustments), 200

@app.route("/api/adjustments", methods=["POST"])
def create_adjustment():
    data = request.json or {}
    product_id = data.get("product_id")
    location_id = data.get("location_id")
    physical_quantity = data.get("physical_quantity")
    reason = data.get("reason", "Physical Stock Audit")

    if product_id is None or location_id is None or physical_quantity is None:
        return jsonify({"error": "Product, Location, and Physical Quantity are required."}), 400

    try:
        res = StockEngine.validate_adjustment(
            product_id=int(product_id),
            location_id=int(location_id),
            physical_quantity=int(physical_quantity),
            reason=reason,
            user_id=1
        )
        return jsonify({
            "message": f"Stock adjustment {res['reference_number']} confirmed.",
            "data": res
        }), 201
    except StockEngineError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Server error processing adjustment."}), 500

# ----------------------------------------------------
# DASHBOARD APIS (KPIs, FILTERS, LOW STOCK)
# ----------------------------------------------------
@app.route("/api/dashboard/summary", methods=["GET"])
def get_dashboard_summary():
    conn = get_db()
    cursor = conn.cursor()

    # Total stock quantity across all products
    cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM stock")
    total_stock_qty = cursor.fetchone()[0]

    # Total distinct products count
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products_count = cursor.fetchone()[0]

    # Calculate Low Stock and Out of Stock products
    cursor.execute('''
    SELECT p.id, p.reorder_level, COALESCE(SUM(s.quantity), 0) as current_stock
    FROM products p
    LEFT JOIN stock s ON p.id = s.product_id
    GROUP BY p.id
    ''')
    prod_stocks = cursor.fetchall()

    low_stock_count = 0
    out_of_stock_count = 0

    for ps in prod_stocks:
        st = ps["current_stock"]
        ro = ps["reorder_level"]
        if st == 0:
            out_of_stock_count += 1
            low_stock_count += 1
        elif st <= ro:
            low_stock_count += 1

    # Pending Receipts (WAINTING / READY)
    cursor.execute("SELECT COUNT(*) FROM receipts WHERE status IN ('DRAFT', 'WAITING', 'READY')")
    pending_receipts = cursor.fetchone()[0]

    # Pending Deliveries (WAITING / READY)
    cursor.execute("SELECT COUNT(*) FROM deliveries WHERE status IN ('DRAFT', 'WAITING', 'READY')")
    pending_deliveries = cursor.fetchone()[0]

    # Scheduled Internal Transfers
    cursor.execute("SELECT COUNT(*) FROM transfers WHERE status IN ('DRAFT', 'WAITING', 'READY')")
    pending_transfers = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        "total_stock_quantity": total_stock_qty,
        "total_products_count": total_products_count,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "pending_receipts": pending_receipts,
        "pending_deliveries": pending_deliveries,
        "pending_transfers": pending_transfers
    }), 200

@app.route("/api/dashboard/low-stock", methods=["GET"])
def get_low_stock_alerts():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT p.id, p.name, p.sku, p.unit_of_measure, p.reorder_level, c.name as category_name,
           COALESCE(SUM(s.quantity), 0) as current_stock
    FROM products p
    JOIN categories c ON p.category_id = c.id
    LEFT JOIN stock s ON p.id = s.product_id
    GROUP BY p.id
    HAVING current_stock <= p.reorder_level
    ORDER BY current_stock ASC
    ''')
    rows = cursor.fetchall()
    low_stock_list = []
    for r in rows:
        item = row_to_dict(r)
        item["status"] = "OUT OF STOCK" if item["current_stock"] == 0 else "LOW STOCK"
        low_stock_list.append(item)

    conn.close()
    return jsonify(low_stock_list), 200

@app.route("/api/dashboard/operations", methods=["GET"])
def get_recent_operations():
    doc_type = request.args.get("doc_type") # Receipts, Delivery, Internal, Adjustments
    status_filter = request.args.get("status")
    warehouse_id = request.args.get("warehouse_id")
    category_id = request.args.get("category_id")

    conn = get_db()
    cursor = conn.cursor()

    ops = []

    # Receipts
    if not doc_type or doc_type in ("All", "Receipts"):
        q = '''
        SELECT r.id, r.reference_number, 'Receipt' as type, r.supplier as party,
               r.status, r.created_at, w.name as warehouse_name
        FROM receipts r
        JOIN warehouses w ON r.warehouse_id = w.id
        WHERE 1=1
        '''
        params = []
        if status_filter and status_filter != "All":
            q += " AND r.status = ?"
            params.append(status_filter)
        if warehouse_id and warehouse_id != "All":
            q += " AND r.warehouse_id = ?"
            params.append(warehouse_id)
        cursor.execute(q, params)
        for r in cursor.fetchall():
            ops.append(row_to_dict(r))

    # Deliveries
    if not doc_type or doc_type in ("All", "Delivery"):
        q = '''
        SELECT d.id, d.reference_number, 'Delivery' as type, d.customer as party,
               d.status, d.created_at, w.name as warehouse_name
        FROM deliveries d
        JOIN warehouses w ON d.warehouse_id = w.id
        WHERE 1=1
        '''
        params = []
        if status_filter and status_filter != "All":
            q += " AND d.status = ?"
            params.append(status_filter)
        if warehouse_id and warehouse_id != "All":
            q += " AND d.warehouse_id = ?"
            params.append(warehouse_id)
        cursor.execute(q, params)
        for r in cursor.fetchall():
            ops.append(row_to_dict(r))

    # Transfers
    if not doc_type or doc_type in ("All", "Internal"):
        q = '''
        SELECT t.id, t.reference_number, 'Internal Transfer' as type,
               (l1.name || ' ➔ ' || l2.name) as party,
               t.status, t.created_at, w1.name as warehouse_name
        FROM transfers t
        JOIN locations l1 ON t.source_location_id = l1.id
        JOIN locations l2 ON t.destination_location_id = l2.id
        JOIN warehouses w1 ON l1.warehouse_id = w1.id
        WHERE 1=1
        '''
        params = []
        if status_filter and status_filter != "All":
            q += " AND t.status = ?"
            params.append(status_filter)
        cursor.execute(q, params)
        for r in cursor.fetchall():
            ops.append(row_to_dict(r))

    # Adjustments
    if not doc_type or doc_type in ("All", "Adjustments"):
        q = '''
        SELECT a.id, a.reference_number, 'Adjustment' as type,
               (p.name || ' (' || a.reason || ')') as party,
               a.status, a.created_at, w.name as warehouse_name
        FROM adjustments a
        JOIN products p ON a.product_id = p.id
        JOIN locations l ON a.location_id = l.id
        JOIN warehouses w ON l.warehouse_id = w.id
        WHERE 1=1
        '''
        params = []
        if status_filter and status_filter != "All":
            q += " AND a.status = ?"
            params.append(status_filter)
        cursor.execute(q, params)
        for r in cursor.fetchall():
            ops.append(row_to_dict(r))

    # Sort combined ops by created_at DESC
    ops.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    conn.close()

    return jsonify(ops[:30]), 200

# ----------------------------------------------------
# STOCK LEDGER APIS (MOVE HISTORY / AUDIT LOG)
# ----------------------------------------------------
@app.route("/api/ledger", methods=["GET"])
def get_ledger():
    product_id = request.args.get("product_id")
    operation_type = request.args.get("operation_type")
    location_id = request.args.get("location_id")
    search = request.args.get("search", "").strip()

    conn = get_db()
    cursor = conn.cursor()

    query = '''
    SELECT sl.*, p.name as product_name, p.unit_of_measure, u.name as user_name,
           l1.name as source_location_name, l1.code as source_location_code,
           l2.name as destination_location_name, l2.code as destination_location_code
    FROM stock_ledger sl
    JOIN products p ON sl.product_id = p.id
    LEFT JOIN users u ON sl.user_id = u.id
    LEFT JOIN locations l1 ON sl.source_location_id = l1.id
    LEFT JOIN locations l2 ON sl.destination_location_id = l2.id
    WHERE 1=1
    '''
    params = []

    if product_id:
        query += " AND sl.product_id = ?"
        params.append(product_id)

    if operation_type and operation_type != "All":
        query += " AND sl.operation_type = ?"
        params.append(operation_type)

    if location_id and location_id != "All":
        query += " AND (sl.source_location_id = ? OR sl.destination_location_id = ?)"
        params.extend([location_id, location_id])

    if search:
        query += " AND (p.name LIKE ? OR sl.sku LIKE ? OR sl.reference_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY sl.id DESC"

    cursor.execute(query, params)
    ledger_items = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify(ledger_items), 200

@app.route("/api/ledger/product/<int:prod_id>", methods=["GET"])
def get_product_ledger(prod_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT sl.*, p.name as product_name, p.unit_of_measure, u.name as user_name,
           l1.name as source_location_name, l2.name as destination_location_name
    FROM stock_ledger sl
    JOIN products p ON sl.product_id = p.id
    LEFT JOIN users u ON sl.user_id = u.id
    LEFT JOIN locations l1 ON sl.source_location_id = l1.id
    LEFT JOIN locations l2 ON sl.destination_location_id = l2.id
    WHERE sl.product_id = ?
    ORDER BY sl.id DESC
    ''', (prod_id,))
    ledger_items = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify(ledger_items), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"StockSense Flask Backend listening on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
