# ============================================================
#  07_cbf_model.py — نموذج التصفية القائمة على المحتوى
#  الأمر: python 07_cbf_model.py
#
#  الفكرة:
#  الusers لديه هدف يومي (مثلاً: 500 kcal للغداء، 40g protein)
#  النموذج يجد الأطعمة التي تشبه هذا Goal أكثر من غيرها
#  باستخدام Cosine Similarity
# ============================================================

import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
from config import DATA_DIR, MODEL_DIR

import importlib.util, sys

def _import_user_profiler():
    spec = importlib.util.spec_from_file_location(
        "up", Path(__file__).parent / "05_user_profiler.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _import_meal_rules():
    spec = importlib.util.spec_from_file_location(
        "mr", Path(__file__).parent / "meal_rules.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

meal_rules = _import_meal_rules()

# ── الميزات الغذائية للمقارنة ─────────────────────────────
NUTRIENT_FEATURES = [
    "calories", "protein", "carbs", "fat", "fiber", "sodium"
]

# وزن كل features في حساب التشابه (الprotein والfiber أهم)
FEATURE_WEIGHTS = np.array([1.0, 2.0, 1.0, 1.0, 1.5, 0.5])


class ContentBasedFilter:
    """
    نموذج التصفية القائمة على المحتوى

    الاستخدام:
        cbf = ContentBasedFilter()
        cbf.fit(foods_df)
        recs = cbf.recommend(user, meal="lunch", top_k=5)
    """

    def __init__(self):
        self.scaler      = MinMaxScaler()
        self.food_matrix = None    # مصفوفة ميزات الfoods بعد التطبيع
        self.foods_df    = None    # DataFrame الfoods الأصلي
        self.is_fitted   = False

    def fit(self, foods_df: pd.DataFrame) -> "ContentBasedFilter":
        """تدريب النموذج على قاعدة بيانات الfoods"""
        self.foods_df = foods_df.copy().reset_index(drop=True)

        # استخرج الأعمدة الموجودة فقط
        cols = [c for c in NUTRIENT_FEATURES if c in foods_df.columns]
        X    = foods_df[cols].fillna(0).values.astype(float)

        # طبّق التطبيع
        X_norm = self.scaler.fit_transform(X)

        # طبّق الأوزان
        weights = FEATURE_WEIGHTS[:len(cols)]
        weights = weights / weights.sum()
        self.food_matrix = X_norm * weights
        self.is_fitted   = True

        print(f"  CBF trained on {len(foods_df)} foods "
              f"with {len(cols)} features")
        return self

    def _build_target_vector(self,
                              meal_targets: dict,
                              meal_name: str) -> np.ndarray:
        """
        حوّل أهداف الوجبة إلى متجه ميزات (نفس شكل food_matrix)
        البيانات لكل 100g، لذا نحوّل Goal إلى نسب
        """
        t = meal_targets[meal_name]
        # نفترض حجم وجبة متوسط 300g
        gram = 300
        raw = np.array([
            t["calories"] / gram * 100,  # calories per 100g
            t["protein"]  / gram * 100,
            t["carbs"]    / gram * 100,
            t["fat"]      / gram * 100,
            2.0,                          # هدف الfiber الافتراضي
            500 / gram * 100,             # هدف الصوديوم الافتراضي
        ])
        # طبّق نفس التطبيع
        raw_2d   = raw.reshape(1, -1)
        norm     = self.scaler.transform(raw_2d)[0]
        cols     = [c for c in NUTRIENT_FEATURES
                    if c in self.foods_df.columns]
        weights  = FEATURE_WEIGHTS[:len(cols)]
        weights  = weights / weights.sum()
        return norm * weights

    def recommend(
        self,
        user: "UserProfile",
        meal: str = "lunch",
        top_k: int = 10,
        exclude_ids: list = None,
        meal_target_calories: float | None = None,
    ) -> pd.DataFrame:
        """
        اقتراح أطعمة لوجبة معيّنة

        Parameters:
            user     : كائن UserProfile
            meal     : "breakfast" | "lunch" | "dinner" | "snack"
            top_k    : count التوصيات
            exclude_ids : fdc_id لأطعمة نريد استبعادها (مقترحة سابقاً)
        """
        assert self.is_fitted, "النموذج غير مدرَّب! استدعِ fit() أولاً"

        meal_targets = user.get_meal_targets()
        if meal_target_calories is not None:
            meal_targets = {key: dict(value) for key, value in meal_targets.items()}
            planned_calories = float(meal_targets[meal]["calories"])
            effective_calories = max(0.0, float(meal_target_calories))
            scale = (effective_calories / planned_calories) if planned_calories > 0 else 0.0
            meal_targets[meal] = {
                **meal_targets[meal],
                "calories": effective_calories,
                "protein": float(meal_targets[meal]["protein"]) * scale,
                "carbs": float(meal_targets[meal]["carbs"]) * scale,
                "fat": float(meal_targets[meal]["fat"]) * scale,
            }
        target_vec = self._build_target_vector(meal_targets, meal)

        # احسب التشابه مع كل الأطعمة
        sims = cosine_similarity(
            target_vec.reshape(1, -1), self.food_matrix
        )[0]

        df = self.foods_df.copy()
        df["cbf_score"] = sims

        # ── فلترة صارمة: نوع الوجبة + الحساسية + عدم الرغبة + القيود الصحية ──
        # (هذا يستبدل الفلتر القديم الذي كان يتجاهل allergies/dislikes تمامًا
        #  ولا يمنع ظهور صنف غير مناسب للوجبة أصلاً)
        df = meal_rules.apply_hard_filters(df, user, meal=meal)

        # استبعاد ما سبق اقتراحه
        if exclude_ids:
            df = df[~df["fdc_id"].isin(exclude_ids)]

        # ترجيح ناعم حسب المفضّلات والطابع (تقليدي/عالمي)
        df = meal_rules.apply_soft_boosts(df, user, score_col="cbf_score")

        # حجم حصة واقعي حسب المجموعة الغذائية (بدل clip(50,500) الموحّد)
        cal_target = meal_targets[meal]["calories"]
        df = df.copy()
        portions = df.apply(
            lambda r: meal_rules.compute_portion(
                r["calories"], cal_target, r.get("food_group", "")
            ), axis=1
        )
        df["portion_g"]        = [p[0] for p in portions]
        df["portion_calories"] = [p[1] for p in portions]

        # رتّب وخذ أعلى K
        result = (df.sort_values("cbf_score", ascending=False)
                    .head(top_k)
                    .reset_index(drop=True))

        cols = ["fdc_id", "name", "category", "food_group", "meal_type",
                "calories", "protein", "carbs", "fat", "fiber",
                "portion_g", "portion_calories", "health_score",
                "diabetic_friendly", "low_sodium", "is_high_protein",
                "cbf_score"]
        return result[[c for c in cols if c in result.columns]]

    def save(self, path=None):
        if path is None:
            path = MODEL_DIR / "cbf_model.pkl"
        with open(path, "wb") as f:
            pickle.dump({
                "scaler":       self.scaler,
                "food_matrix":  self.food_matrix,
                "foods_df":     self.foods_df,
            }, f)
        print(f"  ✓ CBF محفوظ: {path}")
        return path

    @classmethod
    def load(cls, path=None) -> "ContentBasedFilter":
        if path is None:
            path = MODEL_DIR / "cbf_model.pkl"
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj              = cls()
        obj.scaler       = data["scaler"]
        obj.food_matrix  = data["food_matrix"]
        obj.foods_df     = data["foods_df"]
        obj.is_fitted    = True
        return obj


def plot_recommendation_chart(recs: pd.DataFrame,
                               meal_label: str,
                               user_name: str):
    """رسم توصيات CBF لوجبة واحدة"""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(f"توصيات {meal_label} لـ {user_name}", fontweight="bold")

    # يسار: أعمدة CBF Score
    top5 = recs.head(5)
    axes[0].barh(
        top5["name"].str[:20][::-1],
        top5["cbf_score"][::-1],
        color="#2a78d6", alpha=0.85
    )
    axes[0].set_title("درجة التشابه CBF Score")
    axes[0].set_xlabel("التشابه مع هدفك الغذائي")

    # يمين: توزيع المغذيات للfoods الأول
    best = recs.iloc[0]
    vals  = [best["protein"], best["carbs"], best["fat"]]
    lbls  = [f"protein\n{vals[0]:.1f}g",
              f"كارب\n{vals[1]:.1f}g",
              f"fat\n{vals[2]:.1f}g"]
    axes[1].pie(vals, labels=lbls, autopct="%1.0f%%",
                colors=["#1baf7a","#eda100","#D85A30"],
                startangle=90)
    axes[1].set_title(f"توزيع مغذيات: {best['name'][:25]}")

    plt.tight_layout()
    path = DATA_DIR / "charts" / "09_cbf_recommendations.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Recommendations chart saved: {path.name}")


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    # استيراد UserProfile
    up_mod = _import_user_profiler()
    UserProfile = up_mod.UserProfile

    print("\n" + "="*52)
    print("  Content-Based Filtering (CBF) Model")
    print("="*52)

    # 1. تحميل بيانات الfoods
    print("\n[1/4] Loading foods_clean.csv...")
    clean_path = DATA_DIR / "foods_clean.csv"
    if not clean_path.exists():
        raise FileNotFoundError("foods_clean.csv غير موجود! شغّل 03_clean_data.py")
    foods = pd.read_csv(clean_path, encoding="utf-8-sig")
    print(f"  {len(foods)} foods loaded")

    # 2. تدريب النموذج
    print("\n[2/4] Training CBF model...")
    cbf = ContentBasedFilter()
    cbf.fit(foods)

    # 3. اختبار بusersَين
    print("\n[3/4] Testing recommendations...")

    # users 1: شاب رياضي
    u1 = UserProfile(
        name="خالد", age=26, gender="male",
        weight=80, height=180, activity_level=4, goal="gain"
    )
    print(f"\n  الusers: {u1.name}")
    print(f"  Goal اليومي: {u1.daily_calories:.0f} kcal")

    for meal in ["breakfast", "lunch", "dinner"]:
        recs = cbf.recommend(u1, meal=meal, top_k=3)
        targets = u1.get_meal_targets()
        print(f"\n  {targets[meal]['label']} "
              f"({targets[meal]['calories']:.0f} cal):")
        for _, r in recs.iterrows():
            print(f"    • {r['name'][:30]:<32} "
                  f"{r['portion_g']:.0f}g → "
                  f"{r['portion_calories']:.0f} cal  "
                  f"[score: {r['cbf_score']:.3f}]")

    plot_recommendation_chart(
        cbf.recommend(u1, meal="lunch", top_k=5),
        "الغداء", u1.name
    )

    # users 2: مريض سكري
    u2 = UserProfile(
        name="أم محمد", age=52, gender="female",
        weight=85, height=160, activity_level=2, goal="lose",
        has_diabetes=True, has_bp=True
    )
    print(f"\n  الusers: {u2.name} (سكري + ضغط)")
    recs2 = cbf.recommend(u2, meal="lunch", top_k=5)
    print(f"  Lunch recommendations:")
    for _, r in recs2.iterrows():
        print(f"    • {r['name'][:30]:<32} "
              f"{r['portion_g']:.0f}g → {r['portion_calories']:.0f} cal")

    # 4. حفظ النموذج
    print("\n[4/4] Saving model...")
    cbf.save()
    print(f"\n  Next: python 08_cf_model.py")