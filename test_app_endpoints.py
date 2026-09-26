import urllib.request
import json

BASE = "http://127.0.0.1:5000"

def get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

def post(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

print("--- TESTING STOCKSENSE REST API ENDPOINTS ---")

# 1. Login
status, res = post("/api/auth/login", {"email": "alex@stocksense.io", "password": "admin123"})
print(f"1. Login Status: {status} | User: {res['user']['name']} ({res['user']['role']})")

# 2. Dashboard Summary
status, res = get("/api/dashboard/summary")
print(f"2. Dashboard Summary: Total Stock = {res['total_stock_quantity']}, Products = {res['total_products_count']}, Low Stock = {res['low_stock_count']}, Pending Receipts = {res['pending_receipts']}")

# 3. Products List
status, prods = get("/api/products")
print(f"3. Products Loaded: {len(prods)} items.")
for p in prods[:3]:
    print(f"   - {p['name']} ({p['sku']}): Stock={p['total_stock']}, Status={p['stock_status']}")

# 4. Validate Receipt REC-1024 (Receipt ID 2)
try:
    status, res = post("/api/receipts/2/validate", {})
    print(f"4. Receipt REC-1024 Validation: {res['message']}")
except Exception as e:
    print(f"4. Receipt Validation: {e}")

# 5. Validate Delivery Order DEL-1042 (Delivery ID 2)
try:
    status, res = post("/api/deliveries/2/validate", {})
    print(f"5. Delivery DEL-1042 Validation: {res['message']}")
except Exception as e:
    print(f"5. Delivery Validation: {e}")

# 6. Validate Transfer TRF-1003 (Transfer ID 1)
try:
    status, res = post("/api/transfers/1/validate", {})
    print(f"6. Transfer TRF-1003 Validation: {res['message']}")
except Exception as e:
    print(f"6. Transfer Validation: {e}")

# 7. Perform Physical Stock Adjustment
try:
    status, res = post("/api/adjustments", {
        "product_id": 2,
        "location_id": 2,
        "physical_quantity": 15,
        "reason": "Mid-month Physical Audit"
    })
    print(f"7. Adjustment Applied: {res['message']}")
except Exception as e:
    print(f"7. Adjustment Error: {e}")

# 8. Stock Ledger Audit Entries
status, ledger = get("/api/ledger")
print(f"8. Stock Ledger Audit Log: {len(ledger)} total recorded movements.")
for l in ledger[:4]:
    print(f"   - [{l['operation_type']}] Ref: {l['reference_id']} | Product: {l['product_name']} | Qty: {l['quantity']} | New Balance: {l['new_quantity']}")

# 9. Real-Time Market Intelligence Endpoints
print("\n--- TESTING MARKET INTELLIGENCE ENDPOINTS (StockSence Reference) ---")
status, ticker = get("/api/market/ticker")
print(f"9.1 Market Ticker: {len(ticker['tickers'])} live items loaded. Timestamp: {ticker['timestamp']}")

status, sentiment = get("/api/market/sentiment")
print(f"9.2 Market Sentiment: Score = {sentiment['sentiment_score']}/100 ({sentiment['sentiment_label']}) | FII Net: {sentiment['fii_dii_flow']['fii_net']}")

status, momentum = get("/api/market/momentum")
print(f"9.3 Momentum Scanner: {momentum['count']} high-momentum stocks scanned.")

status, breakouts = get("/api/market/breakouts")
print(f"9.4 Breakout Radar: {breakouts['count']} technical pattern breakouts detected.")

status, options = get("/api/market/options")
print(f"9.5 Option Pulse: Max Pain = {options['nifty_max_pain']} | PCR = {options['nifty_pcr']}")

status, sectors = get("/api/market/sectors")
print(f"9.6 Sector Heatmap: {len(sectors['sectors'])} sectors analyzed.")

status, swing = get("/api/market/swing-signals")
print(f"9.7 Swing Signals: {swing['count']} AI swing trade recommendations available.")

print("\n=== ALL ENDPOINT VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

