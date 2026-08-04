# ============================================================
#  02b_merge_external.py — دمج ملفات البيانات الخارجية المتعددة
#  الأمر: python 02b_merge_external.py
#
#  ماذا يفعل؟
#  1. يقرأ foods_raw.csv (البيانات الحالية لكي لا تُمسح).
#  2. يبحث في مجلد data/external/ عن أي ملفات CSV جديدة.
#  3. يطبق خوارزمية دقيقة جداً لتصنيف الأطعمة.
#  4. يدمج الجميع، يزيل التكرار، ويحفظ البيانات المحدثة.
# ============================================================

import pandas as pd
from pathlib import Path
from config import DATA_DIR
import re

# ── إعداد المسارات ────────────────────────────────────────
RAW_PATH = DATA_DIR / "foods_raw.csv"
EXTERNAL_DIR = DATA_DIR / "external"
EXTERNAL_DIR.mkdir(exist_ok=True) # إنشاء المجلد إن لم يكن موجوداً

# ── محرك التصنيف الذكي (Advanced Categorization) ──────────
# قاموس يحتوي على الكلمات المفتاحية بالإنجليزية لربطها بالفئات العربية
CATEGORY_RULES = {
    "مشروبات (Beverages)": ["juice", "water", "tea", "coffee", "soda", "drink", "nectar", "lemonade", "ale", "espresso", "cappuccino", "beverage", "bull"],
    "مكسرات وبذور (Nuts & Seeds)": ["seed", "nut", "almond", "peanut", "pistachio", "hazelnut", "chestnut", "walnut", "pecan", "cashew", "macadamia", "flaxseed", "chia", "sesame"],
    "ألبان وبيض (Dairy & Eggs)": ["milk", "cheese", "yogurt", "yoghurt", "egg", "butter", "cream", "whey"],
    "فواكه (Fruits)": ["apple", "orange", "banana", "berry", "grape", "pineapple", "mango", "cherry", "papaya", "apricot", "peach", "melon", "lemon", "lime", "pomegranate", "tangerine", "fruit"],
    "خضروات (Vegetables)": ["tomato", "carrot", "celery", "spinach", "broccoli", "potato", "onion", "garlic", "vegetable", "squash", "pumpkin"],
    "حبوب ومخبوزات (Grains)": ["bread", "rice", "oat", "cereal", "bran", "corn", "grits", "flour", "pasta", "noodle", "muesli", "granola", "amaranth", "tapioca"],
    "لحوم وأسماك (Meat & Fish)": ["beef", "chicken", "pork", "fish", "salmon", "tuna", "clam", "turkey", "lamb", "meat"],
    "حلويات وسناك (Sweets & Snacks)": ["chocolate", "candy", "cookie", "cake", "syrup", "sugar", "pudding", "caramel", "cocoa"],
    "بقوليات (Legumes)": ["bean", "lentil", "chickpea", "pea", "lupin", "fenugreek"],
    "توابل وأعشاب (Spices)": ["cumin", "dill", "fennel", "mustard", "anise", "herb", "spice"],
}

def guess_category_advanced(food_name: str) -> str:
    """خوارزمية تبحث عن الكلمات المفتاحية داخل اسم الطعام لتحديد فئته بدقة"""
    if pd.isna(food_name): return "غير مصنف"
    
    name_lower = str(food_name).lower()
    
    for category, keywords in CATEGORY_RULES.items():
        for kw in keywords:
            # استخدام التعابير القياسية للبحث عن الكلمة ككلمة مستقلة (تجنب التداخل)
            if re.search(rf'\b{kw}\b', name_lower):
                return category
    
    return "أخرى (Other)"


# ── دالة معالجة ملف واحد ──────────────────────────────────
def process_external_file(file_path: Path, file_index: int) -> pd.DataFrame:
    print(f"  > جاري معالجة: {file_path.name}...")
    df = pd.read_csv(file_path)

    # 1. تنظيف الأعمدة غير المفيدة
    if "Unnamed: 0" in df.columns: df = df.drop(columns=["Unnamed: 0"])
    if "Unnamed: 0.1" in df.columns: df = df.drop(columns=["Unnamed: 0.1"])

    # 2. توحيد أسماء الأعمدة (Mapping)
    rename_map = {
        "food": "name", "Caloric Value": "calories", "Fat": "fat",
        "Carbohydrates": "carbs", "Sugars": "sugar", "Protein": "protein",
        "Dietary Fiber": "fiber", "Sodium": "sodium", "Calcium": "calcium", 
        "Iron": "iron"
    }
    df = df.rename(columns=rename_map)

    # التحقق من وجود عمود name
    if "name" not in df.columns:
        print(f"    [!] تحذير: الملف لا يحتوي على عمود 'food' أو 'name'. تم تجاوزه.")
        return pd.DataFrame()

    # 3. إضافة الميزات الناقصة
    # ننشئ ID فريد لكل ملف (مثلاً: EXT_1_0001)
    df["fdc_id"] = [f"EXT_{file_index}_{i:04d}" for i in range(len(df))]
    df["source"] = f"external_{file_path.stem}"
    
    # 4. تطبيق التصنيف الذكي
    df["category"] = df["name"].apply(guess_category_advanced)

    return df


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  دمج البيانات الخارجية (External Data Merger)")
    print("=" * 60)

    # 1. تحميل البيانات الأصلية (USDA + Local)
    if RAW_PATH.exists():
        df_main = pd.read_csv(RAW_PATH, encoding="utf-8-sig")
        print(f"\n[1/3] تم تحميل البيانات الأصلية: {len(df_main):,} طعام.")
    else:
        df_main = pd.DataFrame()
        print("\n[1/3] لم يتم العثور على أطعمة سابقة. سيتم إنشاء ملف جديد.")

    # 2. قراءة كل ملفات CSV في مجلد external
    external_files = list(EXTERNAL_DIR.glob("*.csv"))
    if not external_files:
        print(f"\n[!] لا يوجد ملفات CSV في المجلد: {EXTERNAL_DIR}")
        print("    الرجاء وضع الملفات هناك ثم إعادة التشغيل.")
        exit()

    print(f"\n[2/3] تم العثور على {len(external_files)} ملفات خارجية. جاري الدمج...")
    
    new_dfs = []
    for idx, file_path in enumerate(external_files, start=1):
        processed_df = process_external_file(file_path, idx)
        if not processed_df.empty:
            new_dfs.append(processed_df)

    if not new_dfs:
        print("\n[!] لم يتم استخراج أي بيانات صالحة من الملفات.")
        exit()

    # 3. الدمج النهائي وإزالة التكرارات
    print("\n[3/3] دمج جميع البيانات وإزالة التكرارات...")
    df_combined = pd.concat([df_main] + new_dfs, ignore_index=True)

    # إزالة التكرارات بناءً على الاسم (مع توحيد حالة الأحرف)
    before_len = len(df_combined)
    df_combined["name_lower"] = df_combined["name"].str.strip().str.lower()
    df_combined = df_combined.drop_duplicates(subset=["name_lower"], keep="last")
    df_combined = df_combined.drop(columns=["name_lower"])
    
    duplicates_removed = before_len - len(df_combined)

    # الاحتفاظ بالأعمدة المطلوبة فقط (لمنع دخول أعمدة غريبة من الملفات الخارجية)
    cols_order = ["fdc_id", "name", "category", "source", "calories", "protein", 
                  "carbs", "fat", "fiber", "sugar", "sodium", "calcium", "iron"]
    cols_exist = [c for c in cols_order if c in df_combined.columns]
    df_combined = df_combined[cols_exist]

    # حفظ الملف
    df_combined.to_csv(RAW_PATH, index=False, encoding="utf-8-sig")

    print(f"\n{'=' * 60}")
    print(f"  ✅ اكتمل الدمج بنجاح!")
    print(f"  - تم حذف {duplicates_removed} طعام مكرر.")
    print(f"  - إجمالي الأطعمة الآن في قاعدة البيانات: {len(df_combined):,} طعام.")
    print(f"  - الملف المحفوظ: {RAW_PATH.name}")
    print("=" * 60)
    
    print("\n  نماذج من التصنيف الجديد:")
    samples = df_combined[df_combined["source"].str.contains("external")].sample(min(5, len(df_combined)))
    print(samples[["name", "category"]].to_string(index=False))
    
    print(f"\n  ▶ الخطوة التالية الحتمية: شغّل 03_clean_data.py لفلترة البيانات هندسياً وحساب نقاط الصحة!")