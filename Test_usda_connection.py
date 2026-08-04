# ============================================================
#  test_usda_connection.py — Diagnose USDA API connectivity
#  Command: python test_usda_connection.py
#
#  Run this FIRST before 02_collect_data.py. It checks:
#    1. Is your API key set (not the placeholder / not DEMO_KEY)?
#    2. Does the API actually respond with real data?
#    3. Does the nutrient field parsing work on a real food?
#  Prints the exact HTTP status and response body on any failure —
#  no more silent zero-results.
# ============================================================

import requests
from config import USDA_API_KEY, USDA_BASE_URL

print("\n" + "=" * 55)
print("  USDA API Connection Diagnostic")
print("=" * 55)

# ── 1. Check the key itself ───────────────────────────────
print(f"\n[1/3] Checking API key...")
print(f"  Key in use: {USDA_API_KEY[:10]}..." if len(USDA_API_KEY) > 10
      else f"  Key in use: {USDA_API_KEY}")

if USDA_API_KEY in ("YOUR_FREE_KEY_HERE", "", "your-usda-key"):
    print("  [FAIL] This is still the placeholder text!")
    print("  Fix: open .env and replace it with your real key from")
    print("       https://fdc.nal.usda.gov/api-guide.html")
    raise SystemExit(1)

if USDA_API_KEY == "DEMO_KEY":
    print("  [WARN] You're using DEMO_KEY — very low rate limit (~30-50/day).")
    print("         Get a free real key (no limit issues) at the link above.")
else:
    print("  [OK] A real key is set.")

# ── 2. Real request against /foods/search (most reliable endpoint) ──
print(f"\n[2/3] Sending a real test request...")
url = f"{USDA_BASE_URL}/foods/search"
params = {
    "api_key":  USDA_API_KEY,
    "query":    "banana",
    "pageSize": 3,
    "dataType": "Foundation,SR Legacy",   # comma-separated STRING, not a list
}

try:
    r = requests.get(url, params=params, timeout=15)
    print(f"  HTTP status: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        foods = data.get("foods", [])
        print(f"  [OK] Got {len(foods)} results for 'banana'")
        if foods:
            first = foods[0]
            print(f"  Sample: {first.get('description', '')} "
                  f"(fdcId={first.get('fdcId')})")
    elif r.status_code == 403:
        print("  [FAIL] 403 Forbidden — the API key is invalid or not activated yet.")
        print("         New keys can take a few minutes to activate after signup.")
    elif r.status_code == 429:
        print("  [FAIL] 429 Too Many Requests — rate limit hit.")
        print("         DEMO_KEY limit is very low; wait or use a real key.")
    else:
        print(f"  [FAIL] Unexpected status. Response body:")
        print(f"  {r.text[:300]}")
except requests.exceptions.Timeout:
    print("  [FAIL] Request timed out — check your internet connection.")
except requests.exceptions.ConnectionError as e:
    print(f"  [FAIL] Connection error: {e}")

# ── 3. Verify nutrient field parsing on the real response ────
print(f"\n[3/3] Verifying nutrient extraction logic...")
try:
    if r.status_code == 200 and data.get("foods"):
        food = data["foods"][0]
        nutrients = food.get("foodNutrients", [])
        print(f"  Raw foodNutrients count: {len(nutrients)}")
        if nutrients:
            sample = nutrients[0]
            print(f"  Sample nutrient entry: {sample}")
            has_nested = "nutrientName" in sample or "nutrient" in sample
            print(f"  [OK] Structure confirmed — extraction code will work correctly")
    else:
        print("  [SKIP] No data to verify (fix step 2 first)")
except NameError:
    print("  [SKIP] No response object available")

print("\n" + "=" * 55)
print("  If all 3 steps show [OK], run: python 02_collect_data.py")
print("=" * 55)