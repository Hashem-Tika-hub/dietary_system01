# ============================================================
#  02_collect_data.py — Collect food data from USDA (FIXED)
#  Command: python 02_collect_data.py
#
#  WHAT WAS WRONG BEFORE
#  ──────────────────────
#  1. Nutrient extraction read n["nutrientName"] and n["value"],
#     but the real USDA response nests the name inside
#     n["nutrient"]["name"] and the amount is n["amount"].
#     Every food's calories computed to 0 → the `calories > 0`
#     filter silently dropped 100% of results, even though the
#     HTTP requests themselves were succeeding (200 OK).
#  2. /foods/list with no query just pages through the DB
#     alphabetically — not useful for building a meal-relevant
#     dataset. Switched to /foods/search with real food-group
#     terms (chicken, rice, broccoli, ...) for balanced coverage.
#
#  This version also prints the real HTTP status and a response
#  snippet on any failure — no more silent zero-results.
# ============================================================

import requests
import pandas as pd
import time
from config import (USDA_API_KEY, USDA_BASE_URL, USDA_PAGE_SIZE,
                    USDA_DATA_TYPES, NUTRIENTS_MAP, SEARCH_TERMS, DATA_DIR)

DATA_DIR.mkdir(exist_ok=True)


# ── Fetch one search term ─────────────────────────────────
def fetch_search(term: str, page_size: int = USDA_PAGE_SIZE) -> list:
    """
    Query /foods/search for one term.
    Returns the list under data["foods"] — NOT the whole response.
    """
    url = f"{USDA_BASE_URL}/foods/search"
    params = {
        "api_key":  USDA_API_KEY,
        "query":    term,
        "pageSize": page_size,
        "dataType": USDA_DATA_TYPES,   # comma-separated STRING — this matters
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            print(f"    [!] '{term}' -> HTTP {r.status_code}: {r.text[:150]}")
            return []
        return r.json().get("foods", [])
    except requests.exceptions.Timeout:
        print(f"    [!] '{term}' -> timed out, skipping")
        return []
    except requests.exceptions.RequestException as e:
        print(f"    [!] '{term}' -> {e}")
        return []


# ── Extract nutrients (THE FIX) ───────────────────────────
def extract_nutrients(food_item: dict) -> dict:
    """
    Correctly reads the real USDA response shape:
        foodNutrients: [{ "nutrient": {"name": "..."}, "amount": 1.2 }, ...]
    (Old code looked for "nutrientName" / "value", which don't exist —
    that was the bug. Kept as a fallback here just in case a different
    endpoint ever returns the flatter shape.)
    """
    category = food_item.get("foodCategory", "")
    if isinstance(category, dict):
        category = category.get("description", "")

    result = {
        "fdc_id":   food_item.get("fdcId", ""),
        "name":     food_item.get("description", "").strip(),
        "category": category,
        "source":   food_item.get("dataType", ""),
    }

    lookup = {}
    for n in food_item.get("foodNutrients", []):
        name = n.get("nutrient", {}).get("name", "") or n.get("nutrientName", "")
        value = n.get("amount", None)
        if value is None:
            value = n.get("value", 0)
        lookup[name] = value

    for usda_name, col_name in NUTRIENTS_MAP.items():
        val = lookup.get(usda_name, 0) or 0
        result[col_name] = round(float(val), 2)

    return result


# ── Main collection loop ──────────────────────────────────
def collect_foods() -> pd.DataFrame:
    all_foods  = []
    seen_ids   = set()

    print(f"\n  Collecting foods across {len(SEARCH_TERMS)} search terms...")
    print("  " + "-" * 45)

    for i, term in enumerate(SEARCH_TERMS, 1):
        items = fetch_search(term)
        kept_this_term = 0

        for item in items:
            food_data = extract_nutrients(item)
            fid = food_data["fdc_id"]

            if fid in seen_ids:
                continue
            if food_data["calories"] <= 0:
                continue

            seen_ids.add(fid)
            all_foods.append(food_data)
            kept_this_term += 1

        status = f"{kept_this_term} kept" if kept_this_term else "0 kept [check above]"
        print(f"  [{i:>2}/{len(SEARCH_TERMS)}] '{term}': "
              f"{len(items)} returned -> {status}  (total so far: {len(all_foods)})")

        time.sleep(0.3)   # be polite to the API between requests

    df = pd.DataFrame(all_foods)
    print(f"\n  Total unique USDA foods collected: {len(df)}")
    return df


# ── Expanded local Arabic / Middle Eastern foods ──────────
def add_local_arabic_foods() -> pd.DataFrame:
    """
    Curated local foods — values per 100g from standard nutrition tables.
    Expanded set covering grains, proteins, vegetables, dairy, sweets,
    and breakfast items typical in Middle Eastern diets.
    """
    local_foods = [
        # name, calories, protein, carbs, fat, fiber, sugar, sodium, calcium, iron, category
        ("كسكسي مطبوخ",        112, 3.8,  23.2, 0.2,  1.4, 0.1,  5,   8,   0.4, "حبوب"),
        ("بسبوسة",              396, 6.8,  64.5, 12.9, 1.2, 22,   180, 30,  1.1, "حلويات"),
        ("ملوخية مطبوخة",       35,  2.1,  5.8,  0.4,  2.2, 0.5,  20,  200, 3.1, "خضروات"),
        ("فتة بالدجاج",         245, 14.2, 28.5, 7.8,  1.1, 1.0,  420, 55,  1.8, "أطباق رئيسية"),
        ("شوربة عدس",           87,  5.5,  14.8, 0.8,  3.8, 1.2,  380, 22,  2.2, "شوربات"),
        ("خبز عربي (بيتا)",     275, 9.1,  55.7, 1.2,  2.3, 0.5,  536, 86,  2.7, "خبز"),
        ("فول مدمس",            110, 7.6,  17.2, 0.5,  5.4, 1.5,  240, 61,  2.6, "بقوليات"),
        ("لبن رائب",            61,  3.5,  4.7,  3.3,  0.0, 4.7,  46,  121, 0.1, "ألبان"),
        ("دجاج مشوي (صدر)",     165, 31.0, 0.0,  3.6,  0.0, 0.0,  74,  15,  1.0, "لحوم"),
        ("سمك بلطي مشوي",       128, 26.2, 0.0,  2.7,  0.0, 0.0,  56,  10,  0.6, "أسماك"),
        ("تمر (ميدجول)",        277, 1.8,  74.9, 0.2,  6.7, 66,   1,   64,  0.9, "فواكه"),
        ("أرز أبيض مطبوخ",     130, 2.7,  28.2, 0.3,  0.4, 0.0,  1,   10,  0.2, "حبوب"),
        ("زيت زيتون",           884, 0.0,  0.0,  100,  0.0, 0.0,  2,   1,   0.6, "زيوت"),
        ("بيض مسلوق",           155, 12.6, 1.1,  10.6, 0.0, 1.1,  124, 50,  1.2, "بيض"),
        ("حليب كامل الدسم",     61,  3.2,  4.8,  3.3,  0.0, 5.1,  43,  113, 0.0, "ألبان"),
        ("طماطم طازجة",         18,  0.9,  3.9,  0.2,  1.2, 2.6,  5,   10,  0.3, "خضروات"),
        ("موز",                 89,  1.1,  22.8, 0.3,  2.6, 12,   1,   5,   0.3, "فواكه"),
        ("جبنة بيضاء",         265, 17.6, 3.1,  20.1, 0.0, 0.5,  790, 493, 0.5, "ألبان"),
        ("عدس مطبوخ",           116, 9.0,  20.1, 0.4,  7.9, 1.8,  2,   19,  3.3, "بقوليات"),
        ("خيار",                15,  0.7,  3.6,  0.1,  0.5, 1.7,  2,   16,  0.3, "خضروات"),
        # ── expanded additions ──
        ("حمص بالطحينة",        166, 7.9,  14.3, 9.6,  6.0, 0.3,  379, 49,  1.7, "بقوليات"),
        ("تبولة",               120, 2.5,  15.0, 6.5,  3.2, 1.1,  150, 30,  1.5, "سلطات"),
        ("فتوش",                95,  1.8,  9.2,  6.0,  2.8, 3.0,  140, 25,  0.9, "سلطات"),
        ("كبة مقلية",           310, 15.0, 22.0, 18.0, 1.5, 0.5,  310, 20,  2.0, "أطباق رئيسية"),
        ("مسخن دجاج",           260, 18.0, 24.0, 10.5, 2.0, 1.0,  340, 40,  1.9, "أطباق رئيسية"),
        ("مجدرة",               150, 5.8,  25.0, 3.2,  4.5, 1.0,  200, 25,  1.8, "أطباق رئيسية"),
        ("شاورما دجاج",         220, 20.0, 12.0, 10.0, 1.0, 1.5,  480, 30,  1.4, "أطباق رئيسية"),
        ("لبنة",                140, 5.5,  4.0,  11.5, 0.0, 3.5,  200, 150, 0.2, "ألبان"),
        ("زعتر بزيت",           320, 6.0,  20.0, 25.0, 8.0, 0.5,  400, 200, 4.0, "توابل"),
        ("مناقيش زعتر",         290, 7.5,  40.0, 11.0, 4.0, 1.0,  450, 90,  2.5, "خبز"),
        ("رمان",                83,  1.7,  18.7, 1.2,  4.0, 13.7, 3,   10,  0.3, "فواكه"),
        ("تين طازج",            74,  0.8,  19.2, 0.3,  2.9, 16.3, 1,   35,  0.4, "فواكه"),
        ("مشمش مجفف",           241, 3.4,  62.6, 0.5,  7.3, 53.4, 10,  55,  2.7, "فواكه"),
        ("لوز",                 579, 21.2, 21.6, 49.9, 12.5,4.4,  1,   269, 3.7, "مكسرات"),
        ("جوز",                 654, 15.2, 13.7, 65.2, 6.7, 2.6,  2,   98,  2.9, "مكسرات"),
        ("طحينة",               595, 17.0, 21.2, 53.8, 9.3, 0.5,  115, 426, 9.0, "زيوت"),
        ("متبل باذنجان",        95,  1.9,  8.0,  6.5,  3.5, 2.0,  180, 20,  0.7, "سلطات"),
        ("بطاطا مشوية",         93,  2.0,  21.0, 0.1,  2.2, 1.0,  10,  15,  0.8, "خضروات"),
        ("قرنبيط مطبوخ",        23,  1.8,  4.1,  0.3,  2.0, 1.9,  15,  16,  0.4, "خضروات"),
        ("سبانخ مطبوخة",        23,  2.9,  3.8,  0.3,  2.2, 0.4,  70,  99,  3.6, "خضروات"),
    ]

    rows = []
    for i, (name, cal, pro, carb, fat, fib, sug, sod, cal_mg, iron, cat) in enumerate(local_foods):
        rows.append({
            "fdc_id": f"LOCAL_{i+1:03d}", "name": name, "category": cat,
            "source": "local", "calories": cal, "protein": pro, "carbs": carb,
            "fat": fat, "fiber": fib, "sugar": sug, "sodium": sod,
            "calcium": cal_mg, "iron": iron,
        })
    return pd.DataFrame(rows)


# ── Main ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Data Collection — Phase 1 (fixed)")
    print("=" * 55)

    if USDA_API_KEY in ("YOUR_FREE_KEY_HERE", ""):
        print("\n[!] USDA_API_KEY is still a placeholder in .env")
        print("    Run: python test_usda_connection.py  first")
        raise SystemExit(1)

    print("\n[1/3] Fetching from USDA API (/foods/search)...")
    df_usda = collect_foods()

    print("\n[2/3] Adding local Arabic foods...")
    df_local = add_local_arabic_foods()
    print(f"  Added {len(df_local)} local foods")

    print("\n[3/3] Merging and saving...")
    df_all = pd.concat([df_usda, df_local], ignore_index=True)

    cols_order = ["fdc_id", "name", "category", "source",
                  "calories", "protein", "carbs", "fat",
                  "fiber", "sugar", "sodium", "calcium", "iron"]
    cols_exist = [c for c in cols_order if c in df_all.columns]
    df_all = df_all[cols_exist]

    raw_path = DATA_DIR / "foods_raw.csv"
    df_all.to_csv(raw_path, index=False, encoding="utf-8-sig")

    print(f"\n{'=' * 55}")
    print(f"  Saved to: {raw_path}")
    print(f"  Total foods : {len(df_all)}")
    print(f"  USDA foods  : {len(df_usda)}")
    print(f"  Local foods : {len(df_local)}")
    print("=" * 55)

    if len(df_usda) == 0:
        print("\n  [!] Still 0 from USDA — run this to see exactly why:")
        print("      python test_usda_connection.py")
    else:
        print("\n  Preview:")
        print(df_all[["name", "calories", "protein"]].sample(
            min(5, len(df_all))).to_string(index=False))
        print(f"\n  Next: python 03_clean_data.py")