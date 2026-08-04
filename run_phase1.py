# ============================================================
#  run_phase1.py — تشغيل المرحلة الأولى كاملة بأمر واحد
#
#  الأمر: python run_phase1.py
#
#  يُشغّل الخطوات بالترتيب:
#    01 → اختبار البيئة
#    02 → جمع البيانات من USDA
#    03 → تنظيف البيانات
#    04 → رسم المخططات الاستكشافية
# ============================================================

import subprocess
import sys
import time
from pathlib import Path

STEPS = [
    ("01_test_setup.py",   "اختبار البيئة"),
    ("03_clean_data.py",   "تنظيف البيانات (من local_food_source.csv)"),
    ("04_explore_data.py", "رسم المخططات"),
]
# ملاحظة: 02_collect_data.py (جلب USDA) بات اختياريًا/تكميليًا فقط —
# المصدر الأساسي الآن data/local_food_source.csv (462 صنف محلي موسوم يدويًا)
# شغّله يدويًا فقط لو تريد إضافة مكوّنات خام عامة تكميلية: python 02_collect_data.py

def run_step(script: str, label: str) -> bool:
    """تشغيل خطوة وإظهار النتيجة"""
    print(f"\n{'='*55}")
    print(f"  ▶  {label}  ({script})")
    print(f"{'='*55}")

    start = time.time()
    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,   # اعرض الـ output مباشرة
    )
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"\n  ✓ {label} — completed in {elapsed:.1f}s")
        return True
    else:
        print(f"\n  ✗ {label} — فشل (كود الخطأ: {result.returncode})")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Phase 1 — Full Run")
    print("=" * 55)

    total_start = time.time()
    passed, failed = 0, 0

    for script, label in STEPS:
        if not Path(script).exists():
            print(f"\n  [!] File {script} not found — skipping")
            continue

        success = run_step(script, label)
        if success:
            passed += 1
        else:
            failed += 1
            ans = input(f"\n  Step failed: '{label}'. هل تريد الContinue? (y/n): ")
            if ans.lower() != "y":
                print("\n  Execution stopped.")
                break

    total = time.time() - total_start
    print(f"\n{'='*55}")
    print(f"  Result: {passed} passed, {failed} failed — {total:.0f}s total")
    if failed == 0:
        print("  Phase 1 completed successfully!")
        print("  Ready to move to Phase 2: build ML model")
    print("=" * 55)