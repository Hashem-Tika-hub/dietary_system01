# config.py — Project settings
# ============================================================

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Keys ──────────────────────────────────────────────────
USDA_API_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")

# ── Paths ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
RAW_EXTERNAL_DATA_DIR = RAW_DATA_DIR / "external"
RAW_COLLECTED_DATA_DIR = RAW_DATA_DIR / "collected"
RAW_LOCAL_FOODS_PATH = RAW_DATA_DIR / "local_food_source.csv"
RAW_COLLECTED_FOODS_PATH = RAW_COLLECTED_DATA_DIR / "foods_raw.csv"

PROCESSED_DATA_DIR = DATA_DIR / "processed"
PROCESSED_FOODS_PATH = PROCESSED_DATA_DIR / "foods_clean.csv"

FIXTURES_DATA_DIR = DATA_DIR / "fixtures"
SYNTHETIC_USERS_PATH = FIXTURES_DATA_DIR / "synthetic_users.csv"

OUTPUTS_DATA_DIR = DATA_DIR / "outputs"
ANALYSIS_OUTPUT_DIR = OUTPUTS_DATA_DIR / "analysis"
CHARTS_DIR = ANALYSIS_OUTPUT_DIR / "charts"
DATASET_STATS_PATH = ANALYSIS_OUTPUT_DIR / "dataset_stats.txt"
EVALUATIONS_OUTPUT_DIR = OUTPUTS_DATA_DIR / "evaluations"
EVALUATION_RESULTS_PATH = EVALUATIONS_OUTPUT_DIR / "evaluation_results.csv"
PLAN_EXPORTS_DIR = OUTPUTS_DATA_DIR / "plans"

MODEL_DIR = BASE_DIR / "models"
for directory in (
    DATA_DIR,
    RAW_DATA_DIR,
    RAW_EXTERNAL_DATA_DIR,
    RAW_COLLECTED_DATA_DIR,
    PROCESSED_DATA_DIR,
    FIXTURES_DATA_DIR,
    OUTPUTS_DATA_DIR,
    ANALYSIS_OUTPUT_DIR,
    CHARTS_DIR,
    EVALUATIONS_OUTPUT_DIR,
    PLAN_EXPORTS_DIR,
    MODEL_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

# ── USDA API settings ─────────────────────────────────────
USDA_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
USDA_PAGE_SIZE = 50          # per search term (max 200 allowed by USDA)

# IMPORTANT: dataType must be a COMMA-SEPARATED STRING for GET requests,
# not a Python list — the API's GET parser does not reliably accept
# repeated-key array syntax the way requests.get(params=...) sends it.
USDA_DATA_TYPES = "Foundation,SR Legacy"

# ── Nutrient field mapping ────────────────────────────────
# USDA nutrient names (left) -> our column names (right)
NUTRIENTS_MAP = {
    "Energy": "calories",
    "Protein": "protein",
    "Carbohydrate, by difference": "carbs",
    "Total lipid (fat)": "fat",
    "Fiber, total dietary": "fiber",
    "Sugars, total including NLEA": "sugar",
    "Sodium, Na": "sodium",
    "Calcium, Ca": "calcium",
    "Iron, Fe": "iron",
}

# ── Search terms — one per food group for balanced coverage ──
# Using /foods/search with real terms (instead of /foods/list) gives
# far more useful, diverse, meal-relevant results than blindly paging
# through the database alphabetically.
SEARCH_TERMS = [
    # Proteins
    "chicken breast", "beef", "salmon", "tuna", "shrimp", "eggs",
    "tofu", "lentils", "chickpeas", "black beans",
    # Grains / carbs
    "white rice", "brown rice", "pasta", "oats", "quinoa",
    "whole wheat bread", "potato", "sweet potato",
    # Vegetables
    "broccoli", "spinach", "carrot", "tomato", "cucumber",
    "bell pepper", "zucchini", "cauliflower",
    # Fruits
    "apple", "banana", "orange", "grapes", "dates", "strawberries",
    "watermelon", "mango",
    # Dairy
    "milk", "yogurt", "cheddar cheese", "greek yogurt",
    # Fats / nuts
    "olive oil", "almonds", "walnuts", "avocado", "peanut butter",
]

if __name__ == "__main__":
    print("=" * 45)
    print("  Project settings")
    print("=" * 45)
    print(f"  USDA key    : {USDA_API_KEY[:8]}...")
    print(f"  Search terms: {len(SEARCH_TERMS)}")
    print(f"  Raw data    : {RAW_DATA_DIR}")
    print(f"  Processed   : {PROCESSED_DATA_DIR}")
    print(f"  Outputs     : {OUTPUTS_DATA_DIR}")
    print(f"  Model dir   : {MODEL_DIR}")
    print("=" * 45)
    if USDA_API_KEY in ("DEMO_KEY", "YOUR_FREE_KEY_HERE", ""):
        print("\n[!] Run: python test_usda_connection.py  to diagnose your key")
