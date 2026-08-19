# ============================================================
#  09_hybrid_recommender.py — النظام الهجين الكامل
#  الأمر: python 09_hybrid_recommender.py
#
#  قلب التوصية: CBF افتراضيًا، ثم CF قائم على تفاعل صريح حقيقي عند الجاهزية
#  القيود الصحية الصلبة → ترتيب آمن → خطة أسبوعية
# ============================================================

import pickle
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from config import DATA_DIR, MODEL_DIR
from api.services.recommendation_policy import (
    blend_candidate_scores,
    effective_hybrid_weights,
)

import importlib.util

def _import(filename, alias):
    spec = importlib.util.spec_from_file_location(
        alias, Path(__file__).parent / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

meal_rules = _import("meal_rules.py", "meal_rules")

# ── أوزان الدمج ───────────────────────────────────────────
CBF_WEIGHT = 0.60
CF_WEIGHT  = 0.40

# ── هيكل الخطة الأسبوعية ─────────────────────────────────
DAYS_AR = ["الأحد","الاثنين","الثلاثاء","الأربعاء",
           "الخميس","الجمعة","السبت"]

MEALS   = ["breakfast","lunch","dinner","snack"]
MEALS_AR = {"breakfast":"فطور","lunch":"غداء",
             "dinner":"عشاء","snack":"وجبة خفيفة"}

# يظهر بدل اسم صنف حقيقي عندما تتعذّر تعبئة خانة إلزامية بعد الفلترة —
# نص لا None حتى لا تنكسر أي شيفرة تتعامل مع الاسم كسلسلة (عرض/تصدير)
MISSING_SLOT_LABEL = "(لا يوجد صنف مناسب)"


class HybridRecommender:
    """
    النظام الهجين لاقتراح الأنظمة الغذائية الشخصية

    الاستخدام:
        hr = HybridRecommender()
        hr.load_models()
        plan = hr.generate_weekly_plan(user)
        hr.print_plan(plan, user)
    """

    def __init__(self,
                 cbf_weight: float = CBF_WEIGHT,
                 cf_weight:  float = CF_WEIGHT):
        assert abs(cbf_weight + cf_weight - 1.0) < 1e-6, \
            "مجموع الأوزان يجب أن يساوي 1"
        self.cbf_weight = cbf_weight
        self.cf_weight  = cf_weight
        self.cbf = None
        self.cf  = None
        self.is_ready = False

    def load_models(self):
        """تحميل نموذج المحتوى وتجهيز الترتيب التعاوني الصريح عند الجاهزية."""
        cbf_path = MODEL_DIR / "cbf_model.pkl"
        if not cbf_path.exists():
            raise FileNotFoundError(
                "cbf_model.pkl غير موجود! شغّل: python 07_cbf_model.py"
            )

        # تحميل نموذج المحتوى، وهو بديل cold-start الآمن. لا يُحمَّل نموذج
        # CF القديم لأنه مُدرَّب على تقييمات مصطنعة؛ درجات CF الصحيحة تأتي
        # لاحقًا من تفاعلات صريحة حقيقية عبر ExplicitFeedbackCollaborativeFilter.
        cbf_mod = _import("07_cbf_model.py", "cbf_mod")
        self.cbf = cbf_mod.ContentBasedFilter.load(cbf_path)
        self.cf = None

        self.is_ready = True
        print("  ✓ نموذج CBF loaded")
        print("  ✓ Explicit-feedback CF will activate when data is ready")

    def _score_candidates(self, user, meal: str,
                           exclude_ids: list = None) -> pd.DataFrame:
        """
        يُرجع كل الأطعمة المؤهلة للوجبة (بعد الفلترة الصارمة في CBF/CF)
        مع درجة هجينة، بدون قصّها بعد — القصّ يحدث لاحقًا لكل خانة
        من خانات الطبق على حدة.
        """
        pool = 500  # أكبر من عدد الأطعمة أصلاً => يرجع كل المؤهل بعد الفلترة
        cbf_recs = self.cbf.recommend(
            user, meal=meal, top_k=pool, exclude_ids=exclude_ids
        ).rename(columns={"cbf_score": "raw_cbf"})
        if cbf_recs.empty:
            return cbf_recs.assign(hybrid_score=pd.Series(dtype=float))
        cbf_recs["fdc_id"] = cbf_recs["fdc_id"].astype(str)

        # Never reuse the legacy CF model trained on synthetic ratings. When
        # the explicit-feedback model is ready, API code supplies its scores
        # keyed by external food identifiers; otherwise this frame is empty
        # and policy weights force content-based ranking.
        explicit_scores = getattr(user, "explicit_collaborative_scores", {})
        cf_small = pd.DataFrame(
            [
                {"fdc_id": str(food_id), "raw_cf": float(score)}
                for food_id, score in explicit_scores.items()
            ],
            columns=["fdc_id", "raw_cf"],
        )
        merged = pd.merge(
            cbf_recs[["fdc_id", "name", "category", "food_group",
                      "calories", "protein", "carbs", "fat", "fiber",
                      "health_score", "raw_cbf"]],
            cf_small,
            on="fdc_id", how="left"
        )

        # Explicit feedback is the only valid source of collaborative scores.
        # Hard eligibility filters have already run inside the content model,
        # so no collaborative score can introduce an unsafe candidate.
        weights = effective_hybrid_weights(
            configured_content_weight=self.cbf_weight,
            configured_collaborative_weight=self.cf_weight,
            interaction_count=getattr(user, "interaction_count", 0),
            collaborative_signals_ready=getattr(
                user, "collaborative_signals_ready", False
            ),
        )
        return blend_candidate_scores(merged, weights=weights)

    def recommend_meal(self,
                       user,
                       meal: str,
                       exclude_ids: list = None) -> list:
        """
        يبني "طبق" الوجبة حسب قالب Exchange Lists / USDA MyPlate بدل قائمة
        مسطحة: كل خانة (بروتين/نشويات/خضار...) تاخذ حصتها من هدف سعرات
        الوجبة وتُملأ بأفضل صنف مؤهل لها فقط — هذا يحل مشكلتين معًا:
        (1) عدم تناسب الصنف مع مناسبة الوجبة، (2) الحصص غير الواقعية
        الناتجة عن تحجيم كل صنف لـ100% من الهدف الكامل بمفرده.

        يُرجع قائمة dict (طبق) بدل DataFrame.
        """
        assert self.is_ready, "استدعِ load_models() أولاً"

        meal_targets = user.get_meal_targets()
        cal_target = meal_targets[meal]["calories"]
        template = meal_rules.PLATE_TEMPLATES.get(
            meal, meal_rules.PLATE_TEMPLATES["snack"]
        )

        exclude_ids = list(exclude_ids or [])
        candidates = self._score_candidates(user, meal, exclude_ids=exclude_ids)

        plate = []
        if candidates.empty:
            return plate

        for slot in template:
            slot_target_cal = cal_target * slot["share"]
            eligible = candidates[
                candidates["food_group"].isin(slot["food_group"]) &
                ~candidates["fdc_id"].isin([p["fdc_id"] for p in plate])
            ]
            if eligible.empty:
                if slot.get("optional", False):
                    continue  # خانة اختيارية فعلاً — تجاوزها طبيعي وسليم
                # خانة إلزامية (بروتين/نشويات/خضار...) بلا صنف مؤهل بعد
                # الفلترة الصارمة — سجّلها صراحةً بدل إخفائها بصمت، حتى لا
                # تخرج وجبة "كاملة" وهي في الحقيقة ناقصة خانة أساسية
                plate.append({
                    "fdc_id": None, "name": MISSING_SLOT_LABEL,
                    "category": None, "food_group": slot["food_group"][0],
                    "slot": slot["slot"], "portion_g": 0.0, "calories": 0.0,
                    "protein": 0.0, "carbs": 0.0, "fat": 0.0,
                    "hybrid_score": 0.0, "missing": True,
                })
                continue

            best = eligible.sort_values("hybrid_score", ascending=False).iloc[0]
            portion_g, portion_cal = meal_rules.compute_portion(
                best["calories"], slot_target_cal, best["food_group"]
            )
            plate.append({
                "fdc_id":       best["fdc_id"],
                "name":         best["name"],
                "category":     best["category"],
                "food_group":   best["food_group"],
                "slot":         slot["slot"],
                "portion_g":    float(portion_g),
                "calories":     float(portion_cal),
                "protein":      round(float(best["protein"]) * portion_g / 100, 1),
                "carbs":        round(float(best["carbs"])   * portion_g / 100, 1),
                "fat":          round(float(best["fat"])     * portion_g / 100, 1),
                "hybrid_score": round(float(best["hybrid_score"]), 3),
            })

        return plate

    def generate_weekly_plan(self,
                              user,
                              days: int = 7) -> dict:
        """
        Generating خطة غذائية أسبوعية كاملة باستخدام قوالب الطبق.

        Returns: dict بهيكل:
        {
          "الأحد": {
            "breakfast": [{"name":..., "slot":..., "portion_g":..., ...}, ...],
            "lunch":     [...],
            ...
          },
          ...
        }
        """
        plan = {}
        used_ids = []   # نافذة تنويع متجدّدة عبر الأسبوع (لا تكرار الصنف نفسه قريبًا)

        for day_idx in range(days):
            day_name = DAYS_AR[day_idx % 7]
            plan[day_name] = {}

            for meal in MEALS:
                plate = self.recommend_meal(
                    user, meal=meal,
                    exclude_ids=used_ids[-25:] if used_ids else None
                )
                for item in plate:
                    if item.get("fdc_id") is not None:   # تجاوز خانات "missing"
                        used_ids.append(item["fdc_id"])
                plan[day_name][meal] = plate

        return plan

    def weekly_diversity_report(self, plan: dict) -> dict:
        """تقرير تنوّع مختصر: كم صنف فريد استُخدم، وأكثر الأصناف تكرارًا"""
        from collections import Counter
        names = [f["name"] for meals in plan.values()
                 for foods in meals.values() for f in foods
                 if not f.get("missing")]
        counts = Counter(names)
        missing_count = sum(
            1 for meals in plan.values()
            for foods in meals.values() for f in foods if f.get("missing")
        )
        return {
            "total_servings": len(names),
            "unique_foods": len(counts),
            "most_repeated": counts.most_common(5),
            "missing_slots": missing_count,
        }

    def print_plan(self, plan: dict, user):
        """طباعة الخطة بشكل منسّق في الـ terminal"""
        targets = user.get_meal_targets()
        print(f"\n{'='*62}")
        print(f"  Weekly Meal Plan — {user.name}")
        print(f"  Goal اليومي: {user.daily_calories:.0f} كيلوkcal")
        print(f"{'='*62}")

        for day, meals in plan.items():
            print(f"\n  📅 {day}")
            day_total_cal = 0

            for meal_key, foods in meals.items():
                meal_label  = MEALS_AR.get(meal_key, meal_key)
                target_cal  = targets[meal_key]["calories"]
                actual_cal  = sum(f["calories"] for f in foods)
                day_total_cal += actual_cal

                print(f"    [{meal_label}] target: {target_cal:.0f} cal  "
                      f"→ actual: {actual_cal:.0f} cal")
                for f in foods:
                    slot = f.get("slot", "")
                    print(f"      • ({slot:<10}) {f['name'][:32]:<34}"
                          f"{f['portion_g']:.0f}g → "
                          f"{f['calories']:.0f} cal")

            print(f"    {'─'*50}")
            print(f"    Day total: {day_total_cal:.0f} cal "
                  f"(target: {user.daily_calories:.0f})")

        print(f"\n{'='*62}")

    def plan_to_dataframe(self, plan: dict) -> pd.DataFrame:
        """تحويل الخطة إلى DataFrame للتصدير"""
        rows = []
        for day, meals in plan.items():
            for meal_key, foods in meals.items():
                for f in foods:
                    rows.append({
                        "اليوم":    day,
                        "الوجبة":   MEALS_AR.get(meal_key, meal_key),
                        "الfoods":   f["name"],
                        "حجم الحصة (g)": f["portion_g"],
                        "calories":    f["calories"],
                        "protein":   f["protein"],
                        "كارب":     f["carbs"],
                        "fat":     f["fat"],
                        "درجة الهجين": round(f["hybrid_score"], 3),
                    })
        return pd.DataFrame(rows)

    def plot_weekly_summary(self, plan: dict, user):
        """رسم ملخص بصري للخطة الأسبوعية"""
        days, calories, proteins, carbs, fats = [], [], [], [], []

        for day, meals in plan.items():
            days.append(day[:3])
            day_cal = sum(f["calories"] for m in meals.values() for f in m)
            day_pro = sum(f["protein"]  for m in meals.values() for f in m)
            day_car = sum(f["carbs"]    for m in meals.values() for f in m)
            day_fat = sum(f["fat"]      for m in meals.values() for f in m)
            calories.append(day_cal)
            proteins.append(day_pro)
            carbs.append(day_car)
            fats.append(day_fat)

        fig, axes = plt.subplots(2, 2, figsize=(13, 8))
        fig.suptitle(f"Weekly Plan Summary — {user.name}",
                     fontweight="bold", fontsize=13)

        target = user.daily_calories

        # الcalories اليومية
        ax = axes[0, 0]
        bars = ax.bar(days, calories, color="#2a78d6", alpha=0.85)
        ax.axhline(target, color="#D85A30", lw=2, linestyle="--",
                   label=f"Goal: {target:.0f}")
        for bar, val in zip(bars, calories):
            ax.text(bar.get_x()+bar.get_width()/2, val+20,
                    f"{val:.0f}", ha="center", fontsize=8)
        ax.set_title("الcalories اليومية")
        ax.legend(fontsize=9)

        # الprotein
        ax = axes[0, 1]
        ax.bar(days, proteins, color="#1baf7a", alpha=0.85)
        ax.axhline(user.protein_g, color="#D85A30", lw=2,
                   linestyle="--", label=f"Goal: {user.protein_g:.0f}g")
        ax.set_title("الprotein اليومي (g)")
        ax.legend(fontsize=9)

        # الcarbs
        ax = axes[1, 0]
        ax.bar(days, carbs, color="#eda100", alpha=0.85)
        ax.axhline(user.carbs_g, color="#D85A30", lw=2,
                   linestyle="--", label=f"Goal: {user.carbs_g:.0f}g")
        ax.set_title("الcarbs اليومية (g)")
        ax.legend(fontsize=9)

        # توزيع مغذيات كامل الأسبوع
        ax = axes[1, 1]
        totals  = [sum(proteins), sum(carbs), sum(fats)]
        labels  = [f"protein\n{totals[0]:.0f}g",
                   f"كارب\n{totals[1]:.0f}g",
                   f"fat\n{totals[2]:.0f}g"]
        ax.pie(totals, labels=labels, autopct="%1.0f%%",
               colors=["#1baf7a","#eda100","#D85A30"], startangle=90)
        ax.set_title("توزيع المغذيات (أسبوع كامل)")

        plt.tight_layout()
        path = DATA_DIR / "charts" / "11_weekly_plan.png"
        plt.savefig(path, dpi=140, bbox_inches="tight")
        plt.close()
        print(f"\n  ✓ Weekly plan chart saved: {path.name}")


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    up_mod = _import("05_user_profiler.py", "up")
    UserProfile = up_mod.UserProfile

    print("\n" + "="*62)
    print("  النظام الهجين — Generating الخطة الغذائية الأسبوعية")
    print("="*62)

    # 1. تحميل النماذج
    print("\n[1/4] Loading models...")
    hr = HybridRecommender(cbf_weight=0.60, cf_weight=0.40)
    hr.load_models()

    # 2. تجربة بusersين مختلفين (بينهم users بتفضيلات: لا يحب البحريات، طابع تقليدي)
    test_users = [
        UserProfile(
            name="أحمد",  age=26, gender="male",
            weight=80, height=180,
            activity_level=4, goal="gain",
            dislikes=["بحريات"], cuisine_style="تقليدي"
        ),
        UserProfile(
            name="سارة",  age=42, gender="female",
            weight=78, height=163,
            activity_level=2, goal="lose",
            has_diabetes=True
        ),
    ]

    for user in test_users:
        print(f"\n{'─'*62}")
        user.print_summary()

        # 3. Generating الخطة الأسبوعية
        print(f"\n[3/4] Generating الخطة الأسبوعية لـ {user.name}...")
        plan = hr.generate_weekly_plan(user, days=7)

        # طباعة أول يومين
        partial = {k: plan[k] for k in list(plan.keys())[:2]}
        hr.print_plan(partial, user)

        report = hr.weekly_diversity_report(plan)
        print(f"\n  تنوّع الأسبوع: {report['unique_foods']} صنف فريد "
              f"من أصل {report['total_servings']} حصة")
        print(f"  الأكثر تكرارًا: {report['most_repeated']}")

        # 4. تصدير + مخطط
        df_plan = hr.plan_to_dataframe(plan)
        out_csv = DATA_DIR / f"weekly_plan_{user.name}.csv"
        df_plan.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"\n  ✓ Plan saved: {out_csv.name}")

        hr.plot_weekly_summary(plan, user)

    print(f"\n{'='*62}")
    print("  Phase 2 completed!")
    print("  Next: python 10_evaluate.py")
    print("="*62)