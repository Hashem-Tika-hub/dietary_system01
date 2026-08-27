# ============================================================
#  05_user_profiler.py — حساب احتياجات الusers الغذائية
#  الأمر: python 05_user_profiler.py
#
#  ما الذي يفعله هذا File؟
#  1. يحسب معدل الأيض الأساسي (BMR) بمعادلة Mifflin-St Jeor
#  2. يحسب إجمالي الcalories اليومية (TDEE) حسب Activity
#  3. يوزّع الcalories على الوجبات والمغذيات
#  4. يُنشئ ملف الأمثلة للusersين الاصطناعيين
# ============================================================

import json
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path
from config import SYNTHETIC_USERS_PATH

# ── ثوابت Activity البدني ───────────────────────────────────
ACTIVITY_FACTORS = {
    1: ("خامل",          1.2,   "لا رياضة، عمل مكتبي"),
    2: ("نشاط خفيف",    1.375, "رياضة خفيفة 1-3 أيام/أسبوع"),
    3: ("avg activity",   1.55,  "رياضة 3-5 أيام/أسبوع"),
    4: ("نشاط عالٍ",    1.725, "رياضة شاقة 6-7 أيام/أسبوع"),
    5: ("نشاط مكثّف",   1.9,   "رياضي محترف أو عمل بدني شاق"),
}

# ── أهداف الusers وتوزيع المغذيات ──────────────────────
GOAL_SETTINGS = {
    "lose":     {"cal_adjust": -0.20, "protein": 0.30, "carbs": 0.40, "fat": 0.30, "label": "خسارة وزن"},
    "maintain": {"cal_adjust":  0.00, "protein": 0.25, "carbs": 0.45, "fat": 0.30, "label": "الحفاظ على الوزن"},
    "gain":     {"cal_adjust": +0.15, "protein": 0.30, "carbs": 0.50, "fat": 0.20, "label": "زيادة الكتلة العضلية"},
    "sport":    {"cal_adjust": +0.10, "protein": 0.35, "carbs": 0.45, "fat": 0.20, "label": "أداء رياضي"},
}

# ── توزيع الوجبات ─────────────────────────────────────────
MEAL_DISTRIBUTION = {
    "breakfast": {"ratio": 0.25, "label": "الفطور"},
    "lunch":     {"ratio": 0.35, "label": "الغداء"},
    "dinner":    {"ratio": 0.30, "label": "العشاء"},
    "snack":     {"ratio": 0.10, "label": "وجبة خفيفة"},
}

# ── قيم حدية للصحة ───────────────────────────────────────
HEALTH_LIMITS = {
    "diabetes":  {"max_sugar_per_meal": 10, "max_carbs_per_meal": 45, "label": "السكري"},
    "bp":        {"max_sodium_per_day": 1500, "label": "ضغط الدم"},
    "cholesterol": {"max_fat_pct": 0.25, "label": "الكوليسترول"},
}


def _round_nutrition(value: float, digits: int = 1) -> float:
    """Round nutritional values deterministically using the conventional half-up rule."""
    quantum = Decimal("1").scaleb(-digits)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


# ── كلاس الusers ─────────────────────────────────────────
@dataclass
class UserProfile:
    # بيانات أساسية
    name:            str   = "users"
    age:             int   = 30
    gender:          str   = "male"        # male | female
    weight:          float = 75.0          # كجم
    height:          float = 175.0         # سم
    activity_level:  int   = 2             # 1-5
    goal:            str   = "maintain"    # lose | maintain | gain | sport

    # الحالة الصحية
    has_diabetes:    bool  = False
    has_bp:          bool  = False
    has_cholesterol: bool  = False

    # الحساسيات الطبية (قائمة مفتوحة) — تُستبعد كليًا
    allergies: list = field(default_factory=list)
    # مثال: ["gluten", "lactose", "nuts", "seafood"]

    # عدم الرغبة الشخصية (غير طبي) — نفس آلية الاستبعاد لكن سبب مختلف
    # القيم المتاحة: بحريات, دواجن, لحوم_حمراء, بيض, ألبان, مكسرات, بقوليات, حلويات
    dislikes: list = field(default_factory=list)

    # الأطعمة المفضّلة — لا تستبعد شيئًا، فقط تُرجّح الترتيب (نفس مفردات dislikes)
    favorites: list = field(default_factory=list)

    # الطابع المفضّل للوجبات: "تقليدي" (محلي/عربي) | "عالمي" | "مزيج"
    cuisine_style: Optional[str] = "مزيج"

    # هل يرغب أن تظهر الحلويات كخيار مناسبات (لا تُدرَج في الخطة الأساسية افتراضيًا)
    allow_treats: bool = False

    # ── الحسابات (تُملأ تلقائياً) ───────────────────────
    bmi:             float = field(init=False, default=0.0)
    bmr:             float = field(init=False, default=0.0)
    tdee:            float = field(init=False, default=0.0)
    daily_calories:  float = field(init=False, default=0.0)
    protein_g:       float = field(init=False, default=0.0)
    carbs_g:         float = field(init=False, default=0.0)
    fat_g:           float = field(init=False, default=0.0)

    def __post_init__(self):
        self._validate()
        self._calculate()

    def _validate(self):
        assert 10 <= self.age <= 100,          "العمر خارج النطاق"
        assert self.gender in ["male","female"],"الجنس: male أو female"
        assert 30 <= self.weight <= 300,       "الوزن خارج النطاق"
        assert 100 <= self.height <= 250,      "الطول خارج النطاق"
        assert 1 <= self.activity_level <= 5,  "Activity: 1-5"
        assert self.goal in GOAL_SETTINGS,     f"Goal غير صالح: {self.goal}"
        assert self.cuisine_style in ("تقليدي", "عالمي", "مزيج", None), \
            "cuisine_style: تقليدي أو عالمي أو مزيج"

    def _calculate(self):
        # BMI
        h_m = self.height / 100
        self.bmi = round(self.weight / (h_m ** 2), 1)

        # BMR — Mifflin-St Jeor
        if self.gender == "male":
            self.bmr = 10 * self.weight + 6.25 * self.height - 5 * self.age + 5
        else:
            self.bmr = 10 * self.weight + 6.25 * self.height - 5 * self.age - 161

        # TDEE
        factor = ACTIVITY_FACTORS[self.activity_level][1]
        self.tdee = self.bmr * factor

        # تعديل Goal
        adjust = GOAL_SETTINGS[self.goal]["cal_adjust"]
        self.daily_calories = self.tdee * (1 + adjust)

        # توزيع المغذيات بالجرامات
        g = GOAL_SETTINGS[self.goal]
        self.protein_g = (self.daily_calories * g["protein"]) / 4
        self.carbs_g   = (self.daily_calories * g["carbs"])   / 4
        self.fat_g     = (self.daily_calories * g["fat"])     / 9

        # تقريب موحّد وحتمي للقيم المعروضة وواجهات API.
        for attr in ["bmi", "bmr", "tdee", "daily_calories", "protein_g", "carbs_g", "fat_g"]:
            setattr(self, attr, _round_nutrition(getattr(self, attr), 1))

    def get_meal_targets(self) -> dict:
        """احسب أهداف كل وجبة"""
        targets = {}
        for meal, info in MEAL_DISTRIBUTION.items():
            r = info["ratio"]
            targets[meal] = {
                "label":    info["label"],
                "calories": _round_nutrition(self.daily_calories * r, 0),
                "protein":  _round_nutrition(self.protein_g * r, 1),
                "carbs":    _round_nutrition(self.carbs_g * r, 1),
                "fat":      _round_nutrition(self.fat_g * r, 1),
            }
        return targets

    def get_health_flags(self) -> dict:
        """جمع كل القيود الصحية في dict واحد"""
        flags = {
            "diabetic_friendly": self.has_diabetes,
            "low_sodium":        self.has_bp,
            "low_fat":           self.has_cholesterol,
            "allergies":         self.allergies,
        }
        return flags

    def get_cluster_features(self) -> list:
        """ميزات لخوارزمية K-Means"""
        return [
            self.age,
            self.bmi,
            self.activity_level,
            int(self.has_diabetes),
            int(self.has_bp),
            int(self.has_cholesterol),
            ["lose","maintain","gain","sport"].index(self.goal),
        ]

    def bmi_category(self) -> str:
        if   self.bmi < 18.5: return "نقص في الوزن"
        elif self.bmi < 25.0: return "وزن طبيعي"
        elif self.bmi < 30.0: return "زيادة في الوزن"
        else:                  return "سمنة"

    def print_summary(self):
        goal_label    = GOAL_SETTINGS[self.goal]["label"]
        activity_info = ACTIVITY_FACTORS[self.activity_level]
        meals         = self.get_meal_targets()

        print(f"\n{'='*52}")
        print(f"  ملف الusers: {self.name}")
        print(f"{'='*52}")
        print(f"  Age/Gender  : {self.age} سنة / {'male' if self.gender=='male' else 'female'}")
        print(f"  Weight/Height  : {self.weight}كجم / {self.height}سم")
        print(f"  BMI index    : {self.bmi} ({self.bmi_category()})")
        print(f"  Activity       : {activity_info[0]}")
        print(f"  Goal        : {goal_label}")

        print(f"\n  Daily Requirement:")
        print(f"  {'BMR':<18}: {self.bmr:>7.0f} كيلوkcal")
        print(f"  {'TDEE':<18}: {self.tdee:>7.0f} كيلوkcal")
        print(f"  {'Goal اليومي':<18}: {self.daily_calories:>7.0f} كيلوkcal")
        print(f"  {'protein':<18}: {self.protein_g:>7.1f} g")
        print(f"  {'carbs':<18}: {self.carbs_g:>7.1f} g")
        print(f"  {'fat':<18}: {self.fat_g:>7.1f} g")

        print(f"\n  Meal Distribution:")
        for meal, t in meals.items():
            print(f"  {t['label']:<16}: {t['calories']:>5.0f} cal  |  "
                  f"P:{t['protein']:>5.1f}g  C:{t['carbs']:>5.1f}g  F:{t['fat']:>5.1f}g")

        conditions = []
        if self.has_diabetes:    conditions.append("السكري")
        if self.has_bp:          conditions.append("ضغط الدم")
        if self.has_cholesterol: conditions.append("الكوليسترول")
        if self.allergies:       conditions.append(f"حساسية: {', '.join(self.allergies)}")

        if conditions:
            print(f"\n  Health Conditions: {' | '.join(conditions)}")

        prefs = []
        if self.dislikes:  prefs.append(f"لا يفضّل: {', '.join(self.dislikes)}")
        if self.favorites: prefs.append(f"يفضّل: {', '.join(self.favorites)}")
        prefs.append(f"الطابع: {self.cuisine_style or 'مزيج'}")
        print(f"  Food Preferences  : {' | '.join(prefs)}")
        print(f"{'='*52}")

    def to_dict(self) -> dict:
        return {
            "name": self.name, "age": self.age, "gender": self.gender,
            "weight": self.weight, "height": self.height,
            "activity_level": self.activity_level, "goal": self.goal,
            "has_diabetes": self.has_diabetes, "has_bp": self.has_bp,
            "has_cholesterol": self.has_cholesterol, "allergies": self.allergies,
            "dislikes": self.dislikes, "favorites": self.favorites,
            "cuisine_style": self.cuisine_style, "allow_treats": self.allow_treats,
            "bmi": self.bmi, "bmr": self.bmr, "tdee": self.tdee,
            "daily_calories": self.daily_calories,
            "protein_g": self.protein_g, "carbs_g": self.carbs_g, "fat_g": self.fat_g,
        }


def generate_synthetic_users(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """
    Generating usersين اصطناعيين لتدريب K-Means والـ CF
    يُمثّلون تنوعاً واقعياً في الأعمار والأهداف والحالات الصحية
    """
    rng = np.random.default_rng(seed)
    records = []

    goals    = ["lose", "maintain", "gain", "sport"]
    genders  = ["male", "female"]
    # أوزان احتمالية لكل هدف
    g_probs  = [0.35, 0.30, 0.20, 0.15]

    for i in range(n):
        gender     = rng.choice(genders)
        age        = int(rng.integers(18, 65))
        weight     = round(float(rng.uniform(50, 120)), 1)
        height     = round(float(rng.uniform(155, 195) if gender=="male"
                                 else rng.uniform(150, 180)), 1)
        activity   = int(rng.integers(1, 6))
        goal       = rng.choice(goals, p=g_probs)

        # الأمراض أكثر شيوعاً مع تقدم العمر
        age_factor      = (age - 18) / 47
        has_diabetes    = bool(rng.random() < 0.08 + age_factor * 0.12)
        has_bp          = bool(rng.random() < 0.10 + age_factor * 0.15)
        has_cholesterol = bool(rng.random() < 0.06 + age_factor * 0.10)

        u = UserProfile(
            name=f"user_{i+1:03d}", age=age, gender=gender,
            weight=weight, height=height,
            activity_level=activity, goal=goal,
            has_diabetes=has_diabetes,
            has_bp=has_bp,
            has_cholesterol=has_cholesterol,
        )
        records.append(u.to_dict())

    df = pd.DataFrame(records)
    path = SYNTHETIC_USERS_PATH
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*52)
    print("  User Profile & Nutritional Calculations")
    print("="*52)

    # مثال 1: شاب رياضي
    u1 = UserProfile(
        name="أحمد", age=24, gender="male",
        weight=78, height=178, activity_level=4, goal="gain"
    )
    u1.print_summary()

    # مثال 2: سيدة مصابة بالسكري
    u2 = UserProfile(
        name="فاطمة", age=45, gender="female",
        weight=82, height=162, activity_level=2, goal="lose",
        has_diabetes=True, has_bp=True
    )
    u2.print_summary()

    # Generating الusersين الاصطناعيين
    print("\n  [*] Generating 300 synthetic users for training...")
    df_users = generate_synthetic_users(300)
    print(f"  ✓ synthetic_users.csv — {len(df_users)} users")
    print(f"\n  Goal distribution:")
    print(df_users["goal"].value_counts().to_string())
    print(f"\n  Next: python 06_kmeans_model.py")