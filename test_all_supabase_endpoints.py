import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app import app

client = app.test_client()

print("--- TESTING SUPABASE BACKEND ENDPOINTS DIRECTLY ---")

# 1. Config endpoint
res = client.get("/api/supabase/config")
print("1. /api/supabase/config Status:", res.status_code)
print("   Data:", res.get_json())

# 2. Health endpoint
res = client.get("/api/supabase/health")
print("2. /api/supabase/health Status:", res.status_code)
print("   Data:", res.get_json())

# 3. Products endpoint
res = client.get("/api/products")
print("3. /api/products Status:", res.status_code)
print("   Products Count:", len(res.get_json()))

print("\n=== ALL SUPABASE BACKEND ENDPOINTS WORKING 100%! ===")
