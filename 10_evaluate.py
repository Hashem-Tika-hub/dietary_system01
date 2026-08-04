# ============================================================
#  10_evaluate.py — تقييم دقة النظام
#  الأمر: python 10_evaluate.py
#
#  المقاييس الusersة:
#  1. Precision@K  — من كل K توصية، كم منها صحيحة؟
#  2. Recall@K     — كم من الأطعمة الصحيحة وجدناها؟
#  3. F1-Score     — المتوسط الهارموني بين الاثنين
#  4. دقة الcalories — مدى قرب الخطة من Goal
#  5. Health Score — هل تلتزم التوصيات بالقيود الصحية؟
# ============================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from config import DATA_DIR, MODEL_DIR

import importlib.util

def _import(filename, alias):
    spec = importlib.util.spec_from_file_location(
        alias, Path(__file__).parent / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

meal_rules = _import("meal_rules.py", "meal_rules")


# ── حساب المقاييس ─────────────────────────────────────────

def precision_at_k(recommended: list, relevant: list, k: int) -> float:
    """
    Precision@K = count التوصيات الصحيحة في أول K / K

    مثال:
    recommended = [A, B, C, D, E]   (أول 5 توصيات)
    relevant    = [A, C, F, G]      (ما يريده الusers فعلاً)
    K=5 → صحيحة = {A, C} → Precision@5 = 2/5 = 0.40
    """
    if k == 0:
        return 0.0
    top_k   = recommended[:k]
    hits    = len(set(top_k) & set(relevant))
    return hits / k


def recall_at_k(recommended: list, relevant: list, k: int) -> float:
    """
    Recall@K = count التوصيات الصحيحة في أول K / إجمالي الصحيحة

    نفس المثال:
    Recall@5 = 2 / 4 = 0.50
    """
    if not relevant:
        return 0.0
    top_k   = recommended[:k]
    hits    = len(set(top_k) & set(relevant))
    return hits / len(relevant)


def f1_score(precision: float, recall: float) -> float:
    """F1 = 2 × P × R / (P + R)"""
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def ndcg_at_k(recommended: list, relevant: list, k: int) -> float:
    """
    NDCG@K — يعطي وزناً أكبر للتوصيات الصحيحة في المراتب الأولى
    DCG  = Σ rel_i / log2(i+2)
    NDCG = DCG / IDCG  (مقسوماً على أفضل ترتيب ممكن)
    """
    relevant_set = set(relevant)
    dcg  = sum(1 / np.log2(i + 2) for i, item in enumerate(recommended[:k])
               if item in relevant_set)
    idcg = sum(1 / np.log2(i + 2) for i in range(min(k, len(relevant))))
    return dcg / idcg if idcg > 0 else 0.0


def calorie_accuracy(actual_cal: float, target_cal: float) -> float:
    """
    دقة الcalories = 1 - |actual - target| / target
    كلما اقتربنا من Goal كانت الدقة أعلى (حد أقصى 1.0)
    """
    if target_cal == 0:
        return 0.0
    deviation = abs(actual_cal - target_cal) / target_cal
    return max(0.0, 1.0 - deviation)


def health_compliance_rate(recommendations: pd.DataFrame,
                            user) -> float:
    """
    نسبة Health constraints compliance
    (% الأطعمة المقترحة التي تحترم قيود الحالة الصحية)
    """
    if recommendations.empty:
        return 0.0

    flags   = user.get_health_flags()
    total   = len(recommendations)
    ok      = total   # نبدأ بالافتراض أن الكل ملتزم

    if flags["diabetic_friendly"] and "diabetic_friendly" in recommendations.columns:
        ok = min(ok, recommendations["diabetic_friendly"].sum())
    if flags["low_sodium"] and "low_sodium" in recommendations.columns:
        ok = min(ok, recommendations["low_sodium"].sum())

    return float(ok) / total


def evaluate_system(hr, users: list, foods_df: pd.DataFrame,
                    k_values: list = [5, 10]) -> pd.DataFrame:
    """
    تقييم شامل للنظام على قائمة usersين

    "الأطعمة الصحيحة" (relevant) = الأطعمة التي تحمل health_score > 65
    وتناسب هدف الusers (توليفة بسيطة لمحاكاة التقييم الفعلي)
    """
    results = []

    for user in users:
        flags = user.get_health_flags()

        # حدّد الأطعمة "الصحيحة" لهذا الusers
        relevant_df = foods_df.copy()

        # يجب أن تكون "الصحيحة" مؤهلة لوجبة الغداء أصلاً — وإلا فالمقارنة
        # ظالمة: نقيس recall مقابل أطعمة فطور/عشاء/حلوى لن تظهر أبدًا في
        # توصية غداء بعد الفلترة الصارمة الجديدة حسب نوع الوجبة
        if "meal_type" in relevant_df.columns:
            relevant_df = relevant_df[
                relevant_df["meal_type"].apply(
                    lambda s: "غداء" in meal_rules.meal_type_list(s)
                )
            ]

        # صفّ حسب Goal
        if user.goal in ["lose"]:
            relevant_df = relevant_df[relevant_df["calories"] < 200]
        elif user.goal in ["gain", "sport"]:
            relevant_df = relevant_df[relevant_df["protein"] > 12]

        # قيود صحية
        if flags["diabetic_friendly"] and "diabetic_friendly" in relevant_df.columns:
            relevant_df = relevant_df[relevant_df["diabetic_friendly"]]
        if flags["low_sodium"] and "low_sodium" in relevant_df.columns:
            relevant_df = relevant_df[relevant_df["low_sodium"]]

        relevant_df = relevant_df[relevant_df["health_score"] > 55]
        relevant_ids = relevant_df["fdc_id"].tolist()

        # الطبق الفعلي (تجميع واحد يكفي — لا يعتمد على K، فقالب الوجبة ثابت)
        plate = hr.recommend_meal(user, meal="lunch")
        target = user.get_meal_targets()["lunch"]["calories"]
        actual = sum(item["calories"] for item in plate)
        cal_acc = calorie_accuracy(actual, target)

        for k in k_values:
            # مقاييس الترتيب (Precision/Recall/NDCG) تُقاس على مجمّع الترشيح
            # المُصنَّف بالكامل (نفس منطق "قائمة توصيات مرتّبة" السابق)،
            # بعد الفلترة الصارمة الجديدة (نوع الوجبة + حساسية + عدم رغبة)
            try:
                ranked = hr._score_candidates(user, meal="lunch")
                ranked = ranked.sort_values("hybrid_score", ascending=False)
                rec_ids = ranked["fdc_id"].head(k).tolist()

                prec   = precision_at_k(rec_ids, relevant_ids, k)
                rec    = recall_at_k(rec_ids, relevant_ids, k)
                f1     = f1_score(prec, rec)
                ndcg   = ndcg_at_k(rec_ids, relevant_ids, k)
                hcr    = health_compliance_rate(ranked.head(k), user)

                results.append({
                    "user":          user.name,
                    "goal":          user.goal,
                    "has_diabetes":  user.has_diabetes,
                    "K":             k,
                    "Precision@K":   round(prec, 4),
                    "Recall@K":      round(rec,  4),
                    "F1-Score":      round(f1,   4),
                    "NDCG@K":        round(ndcg, 4),
                    "Calorie_Acc":   round(cal_acc, 4),
                    "Health_Compliance": round(hcr, 4),
                })
            except Exception as e:
                print(f"    [!] Error with {user.name}, K={k}: {e}")

    return pd.DataFrame(results)


def plot_evaluation_results(df: pd.DataFrame):
    """رسم نتائج التقييم"""
    k_groups = df.groupby("K")

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle("نتائج تقييم النظام الهجين", fontweight="bold", fontsize=13)

    colors = ["#2a78d6", "#1baf7a"]
    metrics = [
        ("Precision@K",      "الدقة Precision@K",   axes[0,0]),
        ("Recall@K",         "الاستدعاء Recall@K",  axes[0,1]),
        ("F1-Score",         "F1-Score",             axes[1,0]),
        ("Health_Compliance","الالتزام الصحي",       axes[1,1]),
    ]

    for metric, label, ax in metrics:
        for (k, group), color in zip(k_groups, colors):
            vals = group[metric].values
            ax.bar(
                [f"K={k}\n{v:.1%}" for v in vals][:5],
                vals[:5],
                label=f"K={k}", color=color, alpha=0.8, width=0.35
            )
        # أضف متوسطات
        for k, group in k_groups:
            avg = group[metric].mean()
            ax.axhline(avg, linestyle="--", lw=1.5, alpha=0.7)

        ax.set_title(label, fontweight="bold")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("القيمة (0-1)")
        ax.legend(fontsize=8)

    plt.tight_layout()
    path = DATA_DIR / "charts" / "12_evaluation.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Evaluation chart saved: {path.name}")


def print_summary_table(df: pd.DataFrame):
    """طباعة جدول ملخص التقييم"""
    summary = (df.groupby("K")[
        ["Precision@K","Recall@K","F1-Score","NDCG@K",
         "Calorie_Acc","Health_Compliance"]
    ].mean().round(4))

    print("\n" + "="*70)
    print("  System Evaluation Summary")
    print("="*70)
    print(f"  {'Metric':<22} {'K=5':>10} {'K=10':>10}  Meaning")
    print("  " + "-"*66)

    explanations = {
        "Precision@K":       "Of every K recs, how many correct?",
        "Recall@K":          "Of all correct, how many found?",
        "F1-Score":          "Harmonic mean (Precision + Recall)",
        "NDCG@K":            "Ranking quality (correct items first)",
        "Calorie_Acc":       "مدى تحقيق هدف الcalories",
        "Health_Compliance": "Health constraints compliance",
    }

    for metric in summary.columns:
        vals = summary[metric].values
        k5   = vals[0] if len(vals) > 0 else 0
        k10  = vals[1] if len(vals) > 1 else 0
        exp  = explanations.get(metric, "")
        status = "✓" if max(k5,k10) >= 0.70 else "◐" if max(k5,k10) >= 0.50 else "✗"
        print(f"  {status} {metric:<20} {k5:>10.1%} {k10:>10.1%}  {exp}")

    print("="*70)

    # هل حققنا الفرضية H1؟
    f1_k10 = summary.loc[10,"F1-Score"] if 10 in summary.index else 0
    prec_k10 = summary.loc[10,"Precision@K"] if 10 in summary.index else 0
    print(f"\n  Hypothesis H1 (Precision@10 ≥ 80%): "
          f"{'✓ PASSED' if prec_k10 >= 0.80 else f'◐ Value = {prec_k10:.1%}'}")
    print(f"  Hypothesis H3 (F1 ≥ 70%): "
          f"{'✓ PASSED' if f1_k10 >= 0.70 else f'◐ Value = {f1_k10:.1%}'}")
    print()


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    up_mod = _import("05_user_profiler.py", "up")
    hr_mod = _import("09_hybrid_recommender.py", "hr")
    UserProfile = up_mod.UserProfile
    HybridRecommender = hr_mod.HybridRecommender

    print("\n" + "="*62)
    print("  Hybrid System Evaluation")
    print("="*62)

    # 1. تحميل النماذج
    print("\n[1/4] Loading models...")
    hr = HybridRecommender()
    hr.load_models()

    # 2. تحميل بيانات الfoods
    print("\n[2/4] تحميل بيانات الfoods...")
    foods_df = pd.read_csv(DATA_DIR / "foods_clean.csv", encoding="utf-8-sig")

    # 3. بناء cluster اختبار (10 usersين متنوعين)
    print("\n[3/4] إنشاء cluster الاختبار...")
    test_users = [
        UserProfile("علي",     22, "male",   70, 175, 3, "maintain"),
        UserProfile("لينا",    35, "female", 65, 162, 2, "lose"),
        UserProfile("كريم",    28, "male",   90, 182, 5, "sport"),
        UserProfile("هند",     48, "female", 80, 160, 2, "lose",
                    has_diabetes=True),
        UserProfile("سامي",    55, "male",   88, 172, 2, "maintain",
                    has_bp=True),
        UserProfile("نور",     25, "female", 58, 165, 4, "gain"),
        UserProfile("طارق",    40, "male",   95, 178, 3, "lose",
                    has_cholesterol=True),
        UserProfile("ريم",     30, "female", 72, 168, 3, "maintain"),
        UserProfile("فراس",    20, "male",   68, 180, 4, "gain"),
        UserProfile("أسماء",   60, "female", 74, 158, 1, "maintain",
                    has_diabetes=True, has_bp=True),
    ]
    print(f"  {len(test_users)} users في cluster الاختبار")

    # 4. التقييم
    print("\n[4/4] Running evaluation...")
    df_results = evaluate_system(hr, test_users, foods_df, k_values=[5, 10])

    # حفظ النتائج
    out_path = DATA_DIR / "evaluation_results.csv"
    df_results.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  ✓ Results saved: {out_path.name}")

    # طباعة الملخص
    print_summary_table(df_results)

    # رسم النتائج
    plot_evaluation_results(df_results)

    print("  Phase 2 completed successfully!")
    print("  Files ready for Phase 3 (FastAPI Backend)")