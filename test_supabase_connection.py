import os
from supabase import create_client, Client

url = "https://kzqofhcqpsgtqlwvljdf.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6cW9maGNxcHNndHFsd3ZsamRmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAzOTkxNTcsImV4cCI6MjEwNTk3NTE1N30.-xbhHs05HpZ8HzZ00a-k0ttnBzYvrsKHj_kFcYY_pzQ"

print("--- TESTING SUPABASE CLIENT CONNECTION ---")
try:
    supabase: Client = create_client(url, key)
    res = supabase.table("products").select("*").execute()
    print("[OK] Successfully connected to Supabase Cloud Database!")
    print(f"Products in Supabase: {len(res.data)} items.")
    for p in res.data[:3]:
        print(f"  - {p['name']} ({p['sku']}): Reorder Level = {p['reorder_level']}")
except Exception as e:
    print("Supabase connection test failed:", e)
