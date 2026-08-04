# ============================================================
#  01_test_setup.py — اختبار البيئة
#  شغّل هذا File أولاً للتأكد من أن كل شيء مثبّت صح
#  الأمر: python 01_test_setup.py
# ============================================================

import sys

def check(name, fn):
    """دالة مساعدة لاختبار كل مكتبة"""
    try:
        fn()
        print(f"  [✓] {name}")
        return True
    except Exception as e:
        print(f"  [✗] {name} — الخطأ: {e}")
        return False

print("\n" + "=" * 50)
print("  Project Environment Check")
print("=" * 50)

results = []

# ── 1. Python Version ─────────────────────────────────────
v = sys.version_info
ok = v.major == 3 and v.minor >= 11
print(f"  [{'✓' if ok else '✗'}] Python {v.major}.{v.minor}.{v.micro}")
results.append(ok)

# ── 2. المكتبات الأساسية ──────────────────────────────────
print("\n  Libraries:")

results.append(check("pandas", lambda: __import__("pandas")))
results.append(check("numpy",  lambda: __import__("numpy")))
results.append(check("requests", lambda: __import__("requests")))
results.append(check("sklearn", lambda: __import__("sklearn")))
results.append(check("dotenv", lambda: __import__("dotenv")))

# ── 3. اتصال الإنترنت ─────────────────────────────────────
print("\n  Connectivity:")
import requests

def test_connection():
    r = requests.get("https://api.nal.usda.gov", timeout=5)
    assert r.status_code in [200, 301, 302, 404]

results.append(check("الاتصال with USDA API", test_connection))

# ── 4. الfolderات ───────────────────────────────────────────
print("\n  Directories:")
from pathlib import Path

for folder in ["data", "models", "api", "notebooks"]:
    exists = Path(folder).exists()
    print(f"  [{'✓' if exists else '✗'}] folder {folder}/")
    results.append(exists)

# ── النتيجة النهائية ──────────────────────────────────────
passed = sum(results)
total  = len(results)
print("\n" + "=" * 50)

if passed == total:
    print(f"  Result: {passed}/{total} — All checks passed — environment is ready!")
    print("  Next: run 02_collect_data.py")
else:
    print(f"  Result: {passed}/{total} — Some packages need installation")
    print("  شغّل: pip install -r requirements.txt")

print("=" * 50 + "\n")
