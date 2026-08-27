# ============================================================
#  03_clean_data.py — تنظيف ومعالجة بيانات الfoods
#  الأمر: python 03_clean_data.py
#
#  ما الذي يفعله هذا File؟
#  1. يقرأ local_food_source.csv من طبقة البيانات الخام
#  2. ينظف البيانات: يُزيل التكرارات والقيم الشاذة
#  3. يضيف حسابات جديدة: BMI، توزيع المغذيات
#  4. يصنّف الأطعمة (صحي / متوسط / عالي الcalories)
#  5. يحفظ النتيجة في data/processed/foods_clean.csv
# ============================================================

import pandas as pd
import numpy as np
from pathlib import Path
from api.services.halal_policy import apply_cultural_food_exclusions
from config import DATASET_STATS_PATH, PROCESSED_FOODS_PATH, RAW_LOCAL_FOODS_PATH

# ── إعداد المسارات ────────────────────────────────────────
RAW_PATH = RAW_LOCAL_FOODS_PATH
CLEAN_PATH = PROCESSED_FOODS_PATH
STATS_PATH = DATASET_STATS_PATH

# ── ثوابت التنظيف ─────────────────────────────────────────
# ملاحظة: كانت 5 سابقًا بافتراض "أقل من 5 = بيانات USDA خاطئة"، لكن هذا
# افتراض خاطئ مع مكوّنات حقيقية صفرية السعرات (ماء، ملح، شاي سادة، ستيفيا) —
# تحقّقنا يدويًا أن كل القيم بين 0-5 في هذه القائمة صحيحة وليست أخطاء
MIN_CALORIES = 0
MAX_CALORIES = 900    # أكثر من 900 لكل 100 جرام = زيت خالص (نستبعد)
MAX_PROTEIN  = 100    # الprotein لا يتجاوز 100 جرام لكل 100 جرام
MAX_FAT      = 100
MAX_CARBS    = 100

# ── دوال التنظيف ──────────────────────────────────────────

def load_raw_data() -> pd.DataFrame:
    """تحميل البيانات الخام"""
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"File {RAW_PATH} غير موجود!\n"
            "شغّل أولاً: python 02_collect_data.py"
        )
    df = pd.read_csv(RAW_PATH, encoding="utf-8-sig")
    print(f"  Loaded {len(df):,} records")
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """إزالة الأطعمة المكررة بالاسم"""
    before = len(df)
    # احتفظ بأول ظهور لكل اسم (نظّف المسافات أولاً)
    df["name_clean"] = df["name"].str.strip().str.lower()
    df = df.drop_duplicates(subset="name_clean", keep="first")
    df = df.drop(columns=["name_clean"])
    after = len(df)
    print(f"  Removed {before - after:,} records مكرر — تبقّى {after:,}")
    return df


def remove_invalid_rows(df: pd.DataFrame) -> pd.DataFrame:
    """حذف الصفوف ذات القيم غير المنطقية"""
    before = len(df)

    # شروط الاستبعاد
    mask = (
        (df["calories"].between(MIN_CALORIES, MAX_CALORIES)) &
        (df["protein"].between(0, MAX_PROTEIN)) &
        (df["fat"].between(0, MAX_FAT)) &
        (df["carbs"].between(0, MAX_CARBS)) &
        (df["name"].notna()) &
        (df["name"].str.len() > 2)
    )
    df = df[mask].copy()
    after = len(df)
    print(f"  Removed {before - after:,} records غير صالح — تبقّى {after:,}")
    return df


def fill_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """معالجة القيم الناقصة"""
    numeric_cols = ["calories", "protein", "carbs", "fat",
                    "fiber", "sugar", "sodium", "calcium", "iron"]

    for col in numeric_cols:
        if col in df.columns:
            # القيم الناقصة = صفر (غياب البيانات ≠ غياب المغذي)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # تأكد من أن الcalories غير سالبة (نسمح بصفر: ماء، ملح، مشروبات دايت)
    df = df[df["calories"] >= 0].copy()
    return df


def add_computed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """إضافة حسابات مشتقة مفيدة للنموذج"""

    # ── 1. نسبة الprotein من الcalories ────────────────────────
    # (safe_cal تتجنب القسمة على صفر لأصناف مثل الماء والملح 0 سعرة)
    safe_cal = df["calories"].replace(0, np.nan)
    df["protein_pct"] = ((df["protein"] * 4) / safe_cal * 100).clip(0, 100).round(1).fillna(0)
    df["carbs_pct"]   = ((df["carbs"]   * 4) / safe_cal * 100).clip(0, 100).round(1).fillna(0)
    df["fat_pct"]     = ((df["fat"]     * 9) / safe_cal * 100).clip(0, 100).round(1).fillna(0)

    # ── 2. كثافة الprotein (protein لكل 100 سعرة) ───────────
    df["protein_density"] = ((df["protein"] / safe_cal) * 100).round(2).fillna(0)

    # ── 3. تصنيف الcalories ───────────────────────────────────
    def calorie_label(cal):
        if cal < 100:  return "منخفض"
        if cal < 250:  return "متوسط"
        if cal < 450:  return "مرتفع"
        return "عالي جداً"

    df["calorie_level"] = df["calories"].apply(calorie_label)

    # ── 4. نقاط الصحة (Health Score 0-100) ─────────────────
    # معادلة بسيطة مبنية على: protein↑ fiber↑ سكر↓ fat↓
    score = (
        np.log1p(df["protein"]) * 10   +   # protein أفضل
        np.log1p(df["fiber"])   * 8    -   # fiber ممتازة
        np.log1p(df["sugar"])   * 5    -   # سكر أسوأ
        np.log1p(df["fat"])     * 2        # fat محدودة
    )
    # حوّل للمقياس 0-100
    s_min, s_max = score.min(), score.max()
    if s_max > s_min:
        df["health_score"] = ((score - s_min) / (s_max - s_min) * 100).round(1)
    else:
        df["health_score"] = 50.0

    # ── 5. هل الfoods عالي الprotein؟ ────────────────────────
    df["is_high_protein"] = df["protein"] >= 15   # 15g لكل 100g

    # ── 6. هل Diabetic friendly؟ ─────────────────────────
    #    (سكر < 5g و كارب < 30g لكل 100g)
    df["diabetic_friendly"] = (df["sugar"] < 5) & (df["carbs"] < 30)

    # ── 7. هل Low sodium؟ ─────────────────────────────
    df["low_sodium"] = df["sodium"] < 140  # أقل من 140mg لكل 100g

    return df


def final_cleanup(df: pd.DataFrame) -> pd.DataFrame:
    """ترتيب نهائي للأعمدة وتنسيق البيانات"""

    # ترتيب الأعمدة
    cols_order = [
        "fdc_id", "name", "category", "food_group", "meal_type", "source",
        # المغذيات الأساسية
        "calories", "protein", "carbs", "fat", "fiber",
        "sugar", "sodium", "calcium", "iron",
        # حسابات مشتقة
        "protein_pct", "carbs_pct", "fat_pct",
        "protein_density", "calorie_level", "health_score",
        # علامات تصفية
        "is_high_protein", "diabetic_friendly", "low_sodium",
    ]

    # خذ فقط الأعمدة الموجودة فعلاً
    existing = [c for c in cols_order if c in df.columns]
    df = df[existing].copy()

    # ترتيب حسب الاسم
    df = df.sort_values("name").reset_index(drop=True)

    # تقريب الأرقام
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].round(2)

    return df


def print_stats(df: pd.DataFrame) -> str:
    """طباعة إحصائيات مختصرة عن cluster البيانات"""

    lines = [
        "=" * 55,
        "  Final Dataset Statistics",
        "=" * 55,
        f"  إجمالي الأطعمة          : {len(df):,}",
    ]
    if "source" in df.columns:
        for src, cnt in df["source"].value_counts().items():
            lines.append(f"    {src:<15}: {cnt:,}")
    if "food_group" in df.columns:
        lines.append("")
        lines.append("  توزيع المجموعات الغذائية:")
        for grp, cnt in df["food_group"].value_counts().items():
            lines.append(f"    {grp:<15}: {cnt:,}")
    if "meal_type" in df.columns:
        lines.append("")
        lines.append("  تغطية كل مناسبة (صنف واحد قد يخدم أكثر من مناسبة):")
        for m in ["فطور", "غداء", "عشاء", "سناك", "حلوى"]:
            cnt = df["meal_type"].fillna("").str.contains(m).sum()
            lines.append(f"    {m:<15}: {cnt:,}")
    lines += [
        "",
        "  Calorie level distribution:",
    ]

    for level in ["منخفض", "متوسط", "مرتفع", "عالي جداً"]:
        count = (df["calorie_level"] == level).sum()
        pct   = count / len(df) * 100
        lines.append(f"    {level:<15}: {count:,} ({pct:.1f}%)")

    lines += [
        "",
        "  Nutrients (avg per 100g):",
        f"    calories     : {df['calories'].mean():.1f} كيلوkcal",
        f"    protein    : {df['protein'].mean():.1f} g",
        f"    carbs: {df['carbs'].mean():.1f} g",
        f"    fat      : {df['fat'].mean():.1f} g",
        f"    fiber     : {df['fiber'].mean():.1f} g",
        "",
        "  Health flags:",
        f"    عالي الprotein      : {df['is_high_protein'].sum():,} foods",
        f"    Diabetic friendly : {df['diabetic_friendly'].sum():,} foods",
        f"    Low sodium     : {df['low_sodium'].sum():,} foods",
        "=" * 55,
    ]

    report = "\n".join(lines)
    print(report)
    return report


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Data Cleaning — Phase 1")
    print("=" * 55)

    # 1. تحميل
    print("\n[1/6] Loading raw data...")
    df = load_raw_data()

    # 2. إزالة التكرارات
    print("\n[2/6] Removing duplicates...")
    df = remove_duplicates(df)

    # 3. حذف القيم غير الصالحة
    print("\n[3/6] Filtering invalid values...")
    df = fill_missing_values(df)
    df = remove_invalid_rows(df)

    # 4. إضافة حسابات
    print("\n[4/6] Adding computed columns...")
    df = add_computed_columns(df)
    print(f"  Added {len(df.columns)} columns total")

    # 5. تطبيق القيود الثقافية ثم الترتيب النهائي
    print("\n[5/6] Applying cultural exclusions and final ordering...")
    before_cultural_exclusions = len(df)
    df = apply_cultural_food_exclusions(df)
    print(f"  Excluded {before_cultural_exclusions - len(df):,} foods with explicit pork/alcohol indicators")
    df = final_cleanup(df)

    # 6. حفظ
    print("\n[6/6] Saving results...")
    df.to_csv(CLEAN_PATH, index=False, encoding="utf-8-sig")
    print(f"  ✓ foods_clean.csv — {len(df):,} foods")

    # إحصائيات
    print()
    report = print_stats(df)

    # حفظ التقرير
    STATS_PATH.write_text(report, encoding="utf-8")
    print(f"\n  Report saved to: {STATS_PATH}")

    # معاينة سريعة
    print("\n  Top 5 foods by health score:")
    top = df.nlargest(5, "health_score")[["name", "calories", "protein", "health_score"]]
    print(top.to_string(index=False))

    print(f"\n  Next: run 04_explore_data.py لرؤية البيانات بيانياً")