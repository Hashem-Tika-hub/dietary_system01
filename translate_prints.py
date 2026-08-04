"""
translate_prints.py — Replace Arabic print-statement text with English.
Run once:  python translate_prints.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent

# ── Translation map: Arabic substring → English replacement ──────────────
# Longer strings first so more specific matches win.
T = {
    # ── config.py ────────────────────────────────────────────────────────
    "إعدادات المشروع":                     "Project Settings",
    "مفتاح USDA":                          "USDA Key",
    "مجلد البيانات":                        "Data folder",
    "مجلد النماذج":                         "Models folder",
    "أنت تستخدم DEMO_KEY — حد 30 طلب يومياً": "Using DEMO_KEY — 30 requests/day limit",
    "سجّل على fdc.nal.usda.gov للحصول على مفتاح مجاني": "Get a free key at fdc.nal.usda.gov",
    "المفتاح محمّل بنجاح":                 "API key loaded successfully",

    # ── 01_test_setup.py ─────────────────────────────────────────────────
    "اختبار بيئة المشروع":                 "Project Environment Check",
    "المكتبات:":                            "Libraries:",
    "الاتصال:":                             "Connectivity:",
    "المجلدات:":                            "Directories:",
    "مجلد":                                 "folder",
    "البيئة جاهزة تماماً!":               "All checks passed — environment is ready!",
    "بعض المكتبات تحتاج تثبيت":           "Some packages need installation",
    "الخطوة التالية: شغّل 02_collect_data.py": "Next: run 02_collect_data.py",

    # ── 02_collect_data.py ───────────────────────────────────────────────
    "جمع بيانات الطعام — المرحلة الأولى": "Data Collection — Phase 1",
    "جمع من USDA API...":                  "Fetching from USDA API...",
    "إضافة الأطعمة العربية المحلية...":   "Adding local Arabic foods...",
    "أضفنا":                               "Added",
    "طعام محلي":                            "local foods",
    "دمج وحفظ البيانات...":               "Merging and saving data...",
    "الملف المحفوظ:":                       "Saved to:",
    "إجمالي الأطعمة:":                     "Total foods:",
    "الأعمدة:":                             "Columns:",
    "أطعمة USDA:":                          "USDA foods:",
    "أطعمة محلية:":                         "Local foods:",
    "نموذج من البيانات:":                   "Data preview:",
    "الخطوة التالية: شغّل 03_clean_data.py": "Next: run 03_clean_data.py",
    "جُمع":                                 "fetched",
    "إجمالي:":                              "total:",
    "فارغة — توقف":                        "empty — stopping",
    "جمع بيانات":                           "Collecting",

    # ── 03_clean_data.py ─────────────────────────────────────────────────
    "تنظيف البيانات — المرحلة الأولى":    "Data Cleaning — Phase 1",
    "تحميل البيانات الخام...":             "Loading raw data...",
    "تم تحميل":                            "Loaded",
    "سجل":                                  "records",
    "إزالة التكرارات...":                   "Removing duplicates...",
    "أُزيل":                               "Removed",
    "سجل مكرر — تبقّى":                   "duplicate records — remaining:",
    "تنقية القيم غير المنطقية...":         "Filtering invalid values...",
    "سجل غير صالح — تبقّى":              "invalid records — remaining:",
    "إضافة الحسابات المشتقة...":           "Adding computed columns...",
    "أُضيف":                               "Added",
    "عمود إجمالاً":                         "columns total",
    "الترتيب النهائي للبيانات...":         "Final ordering...",
    "حفظ النتائج...":                       "Saving results...",
    "foods_clean.csv  —":                   "foods_clean.csv —",
    "طعام":                                  "foods",
    "التقرير محفوظ في:":                   "Report saved to:",
    "أعلى 5 أطعمة بأعلى نقاط صحة:":      "Top 5 foods by health score:",
    "الخطوة التالية: شغّل 04_explore_data.py": "Next: run 04_explore_data.py",
    "إجمالي الأطعمة النهائية:":            "Total final foods:",
    "إحصائيات مجموعة البيانات النهائية":   "Final Dataset Statistics",
    "توزيع مستوى السعرات:":               "Calorie level distribution:",
    "المغذيات (متوسط لكل 100g):":          "Nutrients (avg per 100g):",
    "سعرات":                                "calories",
    "بروتين":                               "protein",
    "كربوهيدرات":                           "carbs",
    "دهون":                                  "fat",
    "ألياف":                                 "fiber",
    "علامات مفيدة:":                        "Health flags:",
    "عالي البروتين":                        "High protein",
    "مناسب لمرضى السكري":                   "Diabetic friendly",
    "منخفض الصوديوم":                       "Low sodium",

    # ── 04_explore_data.py ───────────────────────────────────────────────
    "استكشاف البيانات — رسم المخططات":    "Data Exploration — Generating Charts",
    "تحميل البيانات...":                   "Loading data...",
    "محمّل":                               "loaded",
    "رسم المخططات:":                       "Generating charts:",
    "المخططات محفوظة في:":                "Charts saved to:",
    "افتح المجلد لرؤية الصور:":           "Open folder to view charts:",
    "المرحلة الأولى اكتملت بنجاح!":       "Phase 1 completed successfully!",
    "الخطوة التالية: المرحلة الثانية — بناء نموذج ML": "Next: Phase 2 — Build ML model",

    # ── 05_user_profiler.py ──────────────────────────────────────────────
    "ملف المستخدم والحسابات الغذائية":    "User Profile & Nutritional Calculations",
    "توليد":                               "Generating",
    "مستخدم اصطناعي للتدريب...":          "synthetic users for training...",
    "synthetic_users.csv —":               "synthetic_users.csv —",
    "مستخدم":                              "users",
    "توزيع الأهداف:":                      "Goal distribution:",
    "الخطوة التالية: python 06_kmeans_model.py": "Next: python 06_kmeans_model.py",
    "ملف المستخدم:":                        "User profile:",
    "العمر/الجنس":                         "Age/Gender",
    "الوزن/الطول":                         "Weight/Height",
    "مؤشر BMI":                            "BMI index",
    "النشاط":                              "Activity",
    "الهدف":                               "Goal",
    "الاحتياج اليومي:":                    "Daily Requirement:",
    "الهدف اليومي":                        "Daily Target",
    "توزيع الوجبات:":                      "Meal Distribution:",
    "الحالة الصحية:":                      "Health Conditions:",
    "سنة / ذكر":                           "y / male",
    "سنة / أنثى":                          "y / female",
    "ذكر":                                  "male",
    "أنثى":                                 "female",

    # ── 06_kmeans_model.py ───────────────────────────────────────────────
    "نموذج K-Means لتجميع المستخدمين":    "K-Means User Clustering Model",
    "تحميل بيانات المستخدمين...":         "Loading user data...",
    "تجهيز الميزات وتطبيع البيانات...":   "Preparing and normalizing features...",
    "مصفوفة الميزات:":                     "Feature matrix:",
    "ميزة":                                 "features",
    "إيجاد أفضل قيمة K...":               "Finding optimal K...",
    "اختبار قيم K المختلفة:":              "Testing different K values:",
    "أفضل K =":                            "Optimal K =",
    "تدريب K-Means بـ":                   "Training K-Means with",
    "مصفوفة التقييمات (30 مستخدم × 40 طعام) — الأصفر = غير مُقيَّم":
        "Ratings matrix (30 users × 40 foods) — yellow = unrated",
    "وصف المجموعات وحفظ النموذج...":      "Describing clusters and saving model...",
    "وصف المجموعات:":                      "Cluster descriptions:",
    "مجموعة":                               "cluster",
    "عدد":                                   "count",
    "عمر متوسط":                            "avg age",
    "BMI متوسط":                           "avg BMI",
    "نشاط متوسط":                           "avg activity",
    "نموذج K-Means بـ K=":                "K-Means model with K=",
    "اختبار: تنبؤ مجموعة مستخدم جديد":   "Test: predict cluster for new user",
    "المجموعة:":                            "Cluster:",
    "النموذج محفوظ:":                      "Model saved:",
    "Silhouette Score النهائي:":            "Final Silhouette Score:",
    "مخطط الـ Elbow محفوظ:":              "Elbow chart saved:",
    "مخطط المجموعات:":                     "Cluster scatter saved:",
    "الخطوة التالية: python 07_cbf_model.py": "Next: python 07_cbf_model.py",
    "مستخدم محمّل":                        "users loaded",

    # ── 07_cbf_model.py ──────────────────────────────────────────────────
    "نموذج التصفية القائمة على المحتوى (CBF)": "Content-Based Filtering (CBF) Model",
    "تحميل foods_clean.csv...":            "Loading foods_clean.csv...",
    "تدريب نموذج CBF...":                  "Training CBF model...",
    "اختبار التوصيات...":                  "Testing recommendations...",
    "المستخدم:":                            "User:",
    "الهدف اليومي:":                       "Daily target:",
    "كالوري":                               "kcal",
    "حفظ النموذج...":                      "Saving model...",
    "CBF مدرَّب على":                      "CBF trained on",
    "بـ":                                    "with",
    "توصيات الغداء:":                      "Lunch recommendations:",
    "مخطط التوصيات:":                      "Recommendations chart saved:",
    "الخطوة التالية: python 08_cf_model.py": "Next: python 08_cf_model.py",
    "طعام محمّل":                           "foods loaded",
    "محمّل":                               "loaded",

    # ── 08_cf_model.py ───────────────────────────────────────────────────
    "نموذج التصفية التعاونية (CF)":        "Collaborative Filtering (CF) Model",
    "تحميل البيانات...":                   "Loading data...",
    "توليد مصفوفة التقييمات الاصطناعية...": "Generating synthetic ratings matrix...",
    "كثافة التقييمات:":                    "Rating density:",
    "الباقي صفر":                           "rest are zero",
    "Heatmap التقييمات:":                   "Ratings heatmap saved:",
    "تدريب نموذج CF...":                   "Training CF model...",
    "حساب تشابه المستخدمين...":            "Computing user similarity...",
    "CF مدرَّب:":                           "CF trained:",
    "أعلى 7 توصيات:":                      "Top 7 recommendations:",
    "الخطوة التالية: python 09_hybrid_recommender.py": "Next: python 09_hybrid_recommender.py",
    "مصفوفة:":                              "Matrix:",
    "CF محفوظ:":                           "CF saved:",

    # ── 09_hybrid_recommender.py ─────────────────────────────────────────
    "النظام الهجين — توليد الخطة الغذائية الأسبوعية":
        "Hybrid System — Generating Weekly Meal Plan",
    "تحميل النماذج...":                    "Loading models...",
    "نموذج CBF محمّل":                    "CBF model loaded",
    "نموذج CF  محمّل":                    "CF model loaded",
    "توليد الخطة الأسبوعية لـ":           "Generating weekly plan for",
    "الخطة الغذائية الأسبوعية —":         "Weekly Meal Plan —",
    "الهدف اليومي:":                       "Daily target:",
    "كيلوكالوري":                          "kcal",
    "هدف:":                                 "target:",
    "إجمالي اليوم:":                       "Day total:",
    "الخطة محفوظة:":                       "Plan saved:",
    "مخطط الخطة الأسبوعية:":              "Weekly plan chart saved:",
    "المرحلة الثانية اكتملت!":            "Phase 2 completed!",
    "الخطوة التالية: python 10_evaluate.py": "Next: python 10_evaluate.py",
    "ملخص الخطة الأسبوعية —":             "Weekly Plan Summary —",

    # ── 10_evaluate.py ───────────────────────────────────────────────────
    "تقييم دقة النظام الهجين":            "Hybrid System Evaluation",
    "تحميل النماذج...":                    "Loading models...",
    "تحميل بيانات الطعام...":             "Loading food data...",
    "إنشاء مجموعة الاختبار...":           "Building test set...",
    "في مجموعة الاختبار":                  "users in test set",
    "تشغيل التقييم...":                    "Running evaluation...",
    "النتائج محفوظة:":                     "Results saved:",
    "مخطط التقييم:":                       "Evaluation chart saved:",
    "ملخص نتائج تقييم النظام":            "System Evaluation Summary",
    "المقياس":                              "Metric",
    "التفسير":                              "Meaning",
    "من كل K اقتراح، كم كان صحيحاً؟":    "Of every K recs, how many correct?",
    "من الكل الصحيح، كم وجدنا؟":         "Of all correct, how many found?",
    "متوسط هارموني (الدقة + الاستدعاء)":  "Harmonic mean (Precision + Recall)",
    "جودة الترتيب (الصحيح أولاً أفضل)":  "Ranking quality (correct items first)",
    "مدى تحقيق هدف السعرات":              "Calorie target accuracy",
    "الالتزام بالقيود الصحية":            "Health constraints compliance",
    "الفرضية H1 (Precision@10 ≥ 80%):":  "Hypothesis H1 (Precision@10 ≥ 80%):",
    "محققة":                               "PASSED",
    "القيمة =":                            "Value =",
    "الفرضية H3 (F1 ≥ 70%):":             "Hypothesis H3 (F1 ≥ 70%):",
    "المرحلة الثانية اكتملت بنجاح!":      "Phase 2 completed successfully!",
    "الملفات جاهزة للمرحلة الثالثة (FastAPI Backend)":
        "Files ready for Phase 3 (FastAPI Backend)",
    "خطأ مع":                              "Error with",

    # ── run_phase1.py ────────────────────────────────────────────────────
    "المرحلة الأولى — بدء التشغيل الكامل":  "Phase 1 — Full Run",
    "فشلت خطوة":                           "Step failed:",
    "متابعة؟ (y/n):":                      "Continue? (y/n):",
    "تم إيقاف التشغيل.":                   "Execution stopped.",
    "النتيجة:":                             "Result:",
    "نجح،":                                 "passed,",
    "فشل —":                                "failed —",
    "إجمالاً":                              "total",
    "المرحلة الأولى اكتملت بنجاح!":        "Phase 1 completed successfully!",
    "يمكنك الانتقال للمرحلة الثانية: بناء نموذج ML":
        "Ready to move to Phase 2: build ML model",
    "الملف":                                "File",
    "غير موجود — تخطّي":                   "not found — skipping",
    "اكتمل في":                            "completed in",

    # ── run_phase2.py ────────────────────────────────────────────────────
    "المرحلة الثانية — بناء نماذج ML":    "Phase 2 — Building ML Models",
    "المرحلة الثانية اكتملت!":            "Phase 2 completed!",
    "الملفات الناتجة:":                    "Output files:",
    "فشلت":                                 "failed",
    "ملف:":                                 "File:",

    # ── recommender_engine.py ────────────────────────────────────────────
    "نموذج CBF محمّل":                    "CBF model loaded",
    "نموذج CF  محمّل":                    "CF model loaded",
}


def translate_file(path: Path) -> int:
    """Replace Arabic strings inside print() calls. Returns change count."""
    text = path.read_text(encoding="utf-8")
    original = text
    count = 0
    for arabic, english in T.items():
        if arabic in text:
            text = text.replace(arabic, english)
            count += text.count(english) - original.count(english)
            original = text   # update original for next iteration
    if text != path.read_text(encoding="utf-8"):
        path.write_text(text, encoding="utf-8")
    return text != path.read_text(encoding="utf-8")


def main():
    py_files = [
        "config.py",
        "01_test_setup.py",
        "02_collect_data.py",
        "03_clean_data.py",
        "04_explore_data.py",
        "05_user_profiler.py",
        "06_kmeans_model.py",
        "07_cbf_model.py",
        "08_cf_model.py",
        "09_hybrid_recommender.py",
        "10_evaluate.py",
        "run_phase1.py",
        "run_phase2.py",
        "recommender_engine.py",
    ]

    print("Translating print statements: Arabic → English")
    print("-" * 45)
    changed = 0
    for fname in py_files:
        p = ROOT / fname
        if not p.exists():
            print(f"  skip  {fname} (not found)")
            continue
        original = p.read_text(encoding="utf-8")
        new_text  = original
        hits = 0
        for arabic, english in T.items():
            if arabic in new_text:
                new_text = new_text.replace(arabic, english)
                hits += 1
        if new_text != original:
            p.write_text(new_text, encoding="utf-8")
            print(f"  ✓  {fname}  ({hits} replacements)")
            changed += 1
        else:
            print(f"  —  {fname}  (no Arabic prints found)")

    print("-" * 45)
    print(f"Done. {changed} files updated.")


if __name__ == "__main__":
    main()
