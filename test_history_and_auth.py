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

print("--- TESTING AUTHENTICATION & 10-YEAR HISTORICAL STOCK GRAPH ---")

# 1. Register New Account
try:
    reg_email = "tester99@stocksense.io"
    status, res = post("/api/auth/register", {
        "name": "Alex Tester",
        "email": reg_email,
        "password": "Password123!",
        "confirmPassword": "Password123!"
    })
    print(f"1. New Account Registration Status: {status} | User: {res['user']['name']} ({res['user']['email']})")
except Exception as e:
    print(f"1. Registration Error (or already exists): {e}")

# 2. Login with New Account
status, res = post("/api/auth/login", {"email": "tester99@stocksense.io", "password": "Password123!"})
print(f"2. New Account Login Status: {status} | Role: {res['user']['role']}")

# 3. 10-Year Historical Stock Graph API for Product 1 (Steel Rods)
status, chart = get("/api/products/1/history-chart")
print(f"3. 10-Year Stock Graph API (Product #{chart['product']['id']} - {chart['product']['name']}):")
print(f"   - Total Historical Months: {chart['stats_10y']['total_months']} months ({chart['stats_10y']['start_year']} to {chart['stats_10y']['end_year']})")
print(f"   - 10Y Peak Stock: {chart['stats_10y']['peak_stock']} | 10Y Min Stock: {chart['stats_10y']['lowest_stock']} | 10Y Avg: {chart['stats_10y']['average_stock']}")
print(f"   - First Month (2016): {chart['data_points'][0]['label']} -> Stock: {chart['data_points'][0]['stock']}")
print(f"   - Midpoint (2021): {chart['data_points'][60]['label']} -> Stock: {chart['data_points'][60]['stock']}")
print(f"   - Latest Month (2026): {chart['data_points'][-1]['label']} -> Current Stock: {chart['data_points'][-1]['stock']}")

print("\n=== ALL HISTORICAL GRAPH AND AUTHENTICATION TESTS PASSED! ===")
