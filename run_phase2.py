# ============================================================
#  run_phase2.py — تشغيل المرحلة الثانية كاملة بأمر واحد
#  الأمر: python run_phase2.py
# ============================================================

import subprocess, sys, time
from pathlib import Path

STEPS = [
    ("05_user_profiler.py",    "ملف الusers وGenerating البيانات"),
    ("06_kmeans_model.py",     "نموذج K-Means للتجميع"),
    ("07_cbf_model.py",        "نموذج التصفية بالمحتوى CBF"),
    ("08_cf_model.py",         "نموذج التصفية التعاونية CF"),
    ("09_hybrid_recommender.py","النظام الهجين + الخطة الأسبوعية"),
    ("10_evaluate.py",         "تقييم دقة النظام"),
]

def run(script, label):
    print(f"\n{'='*58}")
    print(f"  ▶  {label}")
    print(f"  File: {script}")
    print(f"{'='*58}")
    t = time.time()
    r = subprocess.run([sys.executable, script])
    elapsed = time.time() - t
    ok = r.returncode == 0
    print(f"\n  {'✓' if ok else '✗'} {label} — {elapsed:.1f}s")
    return ok

if __name__ == "__main__":
    print("\n" + "="*58)
    print("  Phase 2 — Building ML Models")
    print("="*58)

    t_start = time.time()
    passed, failed = 0, 0

    for script, label in STEPS:
        if not Path(script).exists():
            print(f"\n  [!] {script} not found — skipping")
            continue
        if run(script, label):
            passed += 1
        else:
            failed += 1
            ans = input(f"\n  failed '{label}'. Continue? (y/n): ")
            if ans.lower() != "y":
                break

    total = time.time() - t_start
    print(f"\n{'='*58}")
    print(f"  Result: {passed} passed, {failed} failed — {total:.0f}s")
    if failed == 0:
        print("  Phase 2 completed! ✓")
        print("  Fileات الناتجة:")
        for f in ["models/kmeans_model.pkl","models/cbf_model.pkl",
                  "models/cf_model.pkl","data/outputs/evaluations/evaluation_results.csv"]:
            p = Path(f)
            exists = "✓" if p.exists() else "✗"
            print(f"    {exists} {f}")
    print("="*58)
