# ============================================================
#  meal_rules.py — القواعس المشتركة للتصفية والحصص
#  يُستخدم من 07_cbf_model.py و 08_cf_model.py و 09_hybrid_recommender.py
#
#  يطبّق فعليًا:
#  1) نظام Exchange Lists: مجموعات غذائية + حصص واقعية قياسية لكل مجموعة
#  2) USDA MyPlate: كل وجبة رئيسية = بروتين + نشويات + خضار بنسب محددة
#  3) فلترة صارمة قبل الترتيب الذكي: نوع الوجبة، الحساسية، عدم الرغبة
#  4) تفضيل ناعم (soft boost) للأطعمة المفضّلة والطابع التقليدي/العالمي
# ============================================================

import numpy as np
import pandas as pd

# ── ربط مفاتيح الوجبة الإنجليزية (المستخدمة في بقية الكود) بوسم meal_type
# العربي الفعلي في البيانات — بدون هذا، أي مقارنة بين "breakfast" و"فطور"
# ترجع دائمًا لا شيء
MEAL_KEY_TO_AR = {
    "breakfast": "فطور",
    "lunch":     "غداء",
    "dinner":    "عشاء",
    "snack":     "سناك",
    "dessert":   "حلوى",
}

# ── وسوم المجموعات الغذائية (تُستخدم لـ allergies / dislikes / favorites) ──
# كل مفتاح يُطابق قيم عمود category الموجودة فعليًا في local_food_source.csv
FOOD_GROUP_TAGS = {
    "بحريات":     ["أسماك", "أطباق سمك"],
    "دواجن":      ["دواجن"],
    "لحوم_حمراء": ["لحوم", "لحوم سريعة", "أطباق لحوم"],
    "بيض":        ["بيض", "أطباق بيض"],
    "ألبان":      ["ألبان"],
    "مكسرات":     ["مكسرات"],
    "بقوليات":    ["بقوليات"],
    "حلويات":     ["حلويات", "سكريات", "حلويات/فطور"],
}

# الأسماء المعروضة على المستخدم (للأسئلة/الواجهة) مع نفس المفاتيح أعلاه
FOOD_GROUP_LABELS = {
    "بحريات": "المأكولات البحرية والأسماك",
    "دواجن": "الدجاج والدواجن",
    "لحوم_حمراء": "اللحوم الحمراء",
    "بيض": "البيض",
    "ألبان": "الألبان",
    "مكسرات": "المكسرات",
    "بقوليات": "البقوليات (عدس، فول، حمص...)",
    "حلويات": "الحلويات",
}


def _categories_for_tags(tags: list) -> set:
    """يحوّل قائمة وسوم (مثل ['بحريات','مكسرات']) إلى مجموعة قيم category الفعلية"""
    cats = set()
    for t in tags or []:
        cats.update(FOOD_GROUP_TAGS.get(t, []))
    return cats


# Compatibility aliases for legacy profile values. New catalog imports should
# store canonical allergen codes such as ``allergen.milk`` directly.
ALLERGEN_CODE_ALIASES = {
    "ألبان": {"allergen.milk"},
    "حليب": {"allergen.milk"},
    "بيض": {"allergen.egg"},
    "مكسرات": {"allergen.nuts", "allergen.tree_nuts", "allergen.peanut"},
    "فول سوداني": {"allergen.peanut"},
    "قمح": {"allergen.wheat"},
    "جلوتين": {"allergen.wheat", "allergen.gluten"},
}


def declared_allergen_codes(allergies: list) -> set:
    """Return canonical allergen codes for declared allergy values."""
    codes = set()
    for value in allergies or []:
        key = str(value).strip().lower()
        if key.startswith("allergen."):
            codes.add(key)
        else:
            codes.update(ALLERGEN_CODE_ALIASES.get(str(value).strip(), set()))
    return codes


def _as_code_set(value) -> set:
    """Normalize list/set/comma-delimited catalog allergen values."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return {item.strip().lower() for item in str(value).split(",") if item.strip()}


def _has_allergen_conflict(value, declared_codes: set) -> bool:
    return bool(_as_code_set(value) & declared_codes)


# ── قوالب الطبق لكل مناسبة (Exchange Lists + MyPlate) ─────────
# كل قالب = قائمة "خانات"، كل خانة لها food_group مطلوب ونسبة من هدف
# سعرات الوجبة. الخانات غير الأساسية (optional) تُهمَل لو لا يوجد صنف مناسب.
PLATE_TEMPLATES = {
    "breakfast": [
        {"slot": "نشويات",      "food_group": ["نشويات"],           "share": 0.45},
        {"slot": "بروتين/ألبان", "food_group": ["بروتين", "ألبان"],  "share": 0.45},
        {"slot": "فاكهة",       "food_group": ["فواكه"],             "share": 0.10, "optional": True},
    ],
    "lunch": [
        {"slot": "بروتين",  "food_group": ["بروتين"],  "share": 0.35},
        {"slot": "نشويات",  "food_group": ["نشويات"],  "share": 0.40},
        {"slot": "خضار",    "food_group": ["خضار"],    "share": 0.15},
        {"slot": "دهون",    "food_group": ["دهون"],    "share": 0.10, "optional": True},
    ],
    "dinner": [
        {"slot": "بروتين",  "food_group": ["بروتين"],  "share": 0.35},
        {"slot": "نشويات",  "food_group": ["نشويات"],  "share": 0.35},
        {"slot": "خضار",    "food_group": ["خضار"],    "share": 0.20},
        {"slot": "دهون",    "food_group": ["دهون"],    "share": 0.10, "optional": True},
    ],
    "snack": [
        {"slot": "خفيف", "food_group": ["فواكه", "ألبان", "بروتين", "نشويات", "دهون"], "share": 1.0},
    ],
}
# ملاحظة: الخضار تأخذ حصة سعرات أصغر من "نصف الطبق" في MyPlate عمدًا —
# ذلك المبدأ حجمي (نصف الطبق بالحجم) وليس بالسعرات، والخضار منخفضة الكثافة
# السعرية أصلاً، فتخصيص 25-30% من السعرات لها كان يُنتج عجزًا ممنهجًا عن
# الهدف اليومي. الخضار موجودة وجوبًا بكل وجبة رئيسية لكن بحصة سعرات واقعية.

# ── سقوف حصة واقعية لكل مجموعة غذائية (جرام) — بديل clip(50,500) الموحّد ──
# مبنية على مبدأ Exchange Lists: حصة قياسية معقولة بدل حساب حر
PORTION_CAPS_G = {
    "بروتين":  (80, 250),
    "نشويات":  (60, 250),
    "خضار":    (80, 300),
    "فواكه":   (80, 200),
    "ألبان":   (100, 250),
    "دهون":    (5, 30),      # زيوت/مكسرات/سمن — كثيفة السعرات، حصص صغيرة وجوبًا
    "حلويات":  (30, 100),
}
DEFAULT_PORTION_CAP = (50, 300)


def portion_cap_for(food_group: str) -> tuple:
    return PORTION_CAPS_G.get(food_group, DEFAULT_PORTION_CAP)


def get_slot_info(meal: str, slot: str) -> dict:
    """يرجع معلومات خانة معيّنة (المجموعات الغذائية المسموحة + نسبتها من
    هدف الوجبة) بمطابقة اسم الوجبة (breakfast/lunch/dinner/snack) واسم
    الخانة — يُستخدم لميزة استبدال صنف"""
    template = PLATE_TEMPLATES.get(meal, PLATE_TEMPLATES["snack"])
    for s in template:
        if s["slot"] == slot:
            return s
    return None


def compute_portion(calories_per_100g: float, target_calories: float,
                     food_group: str) -> tuple:
    """
    يحسب حجم الحصة (جرام) والسعرات الفعلية لصنف معيّن بحيث يقترب
    من target_calories، لكن مقيَّد بسقف واقعي حسب مجموعته الغذائية.
    يرجع (portion_g, portion_calories)
    """
    lo, hi = portion_cap_for(food_group)
    if calories_per_100g <= 0:
        portion_g = lo
    else:
        portion_g = (target_calories / calories_per_100g) * 100
        portion_g = float(np.clip(portion_g, lo, hi))
    portion_calories = portion_g * calories_per_100g / 100
    return round(portion_g), round(portion_calories)


def meal_type_list(raw: str) -> list:
    """يحوّل نص meal_type ('غداء، عشاء') إلى قائمة نظيفة ['غداء','عشاء']"""
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [x.strip() for x in raw.split("،") if x.strip()]


def apply_hard_filters(df: pd.DataFrame, user, meal: str = None) -> pd.DataFrame:
    """
    خطوة الفلترة الصارمة (Hard Filter) — تُطبَّق قبل أي ترتيب ذكي (CBF/CF).
    هذا هو الجزء الذي كان مفقودًا: allergies/dislikes كانت تُحسب ولا تُستخدم،
    و meal كان يُستخدم فقط لحساب الهدف الرقمي لا لاستبعاد الأطعمة.
    """
    out = df.copy()

    # 1) نوع الوجبة: الصنف مؤهل فقط لو meal ضمن قائمة meal_type الخاصة به
    if meal and "meal_type" in out.columns:
        meal_ar = MEAL_KEY_TO_AR.get(meal, meal)  # يقبل "breakfast" أو "فطور" مباشرة
        out = out[out["meal_type"].apply(lambda s: meal_ar in meal_type_list(s))]

    flags = user.get_health_flags() if hasattr(user, "get_health_flags") else {}

    # 2) الحساسية الطبية — استبعاد كامل. عندما تأتي المرشحات من
    # كتالوج موثق، استخدم رموز مسببات الحساسية بدل التخمين من الفئة.
    declared_codes = declared_allergen_codes(flags.get("allergies", []))
    if declared_codes and "allergen_codes" in out.columns:
        out = out[
            ~out["allergen_codes"].apply(
                lambda value: _has_allergen_conflict(value, declared_codes)
            )
        ]

    # 3) توافق احتياطي مع CSV القديم: بعض الحساسيات كانت ممثلة بفئة الطعام.
    # لا يحل ذلك محل بيانات المكونات/الحساسية الموثقة في الكتالوج الجديد.
    exclude_cats = _categories_for_tags(flags.get("allergies", []))
    exclude_cats |= _categories_for_tags(getattr(user, "dislikes", []) or [])
    if exclude_cats and "category" in out.columns:
        out = out[~out["category"].isin(exclude_cats)]

    # 4) القيود الصحية الموجودة أصلاً (سكري / ضغط / كوليسترول)
    if flags.get("diabetic_friendly") and "diabetic_friendly" in out.columns:
        out = out[out["diabetic_friendly"] == True]
    if flags.get("low_sodium") and "low_sodium" in out.columns:
        out = out[out["low_sodium"] == True]
    if flags.get("low_fat") and "fat_pct" in out.columns:
        out = out[out["fat_pct"] <= 25]

    return out


def apply_soft_boosts(df: pd.DataFrame, user, score_col: str = "hybrid_score") -> pd.DataFrame:
    """
    تفضيلات ناعمة (لا تستبعد، فقط تُرجّح الترتيب):
    - favorites: رفع 15% للأطعمة من فئة مفضّلة
    - cuisine_style: رفع 10% حسب الطابع التقليدي/العالمي المفضّل
    """
    out = df.copy()
    if score_col not in out.columns:
        return out

    fav_cats = _categories_for_tags(getattr(user, "favorites", []) or [])
    if fav_cats and "category" in out.columns:
        out.loc[out["category"].isin(fav_cats), score_col] *= 1.15

    style = getattr(user, "cuisine_style", None)
    if style == "تقليدي" and "source" in out.columns:
        out.loc[out["source"] == "وصفة تقديرية", score_col] *= 1.10
    elif style == "عالمي" and "source" in out.columns:
        out.loc[out["source"] == "قياسي", score_col] *= 1.10
    # "مزيج" أو None -> بدون ترجيح

    return out