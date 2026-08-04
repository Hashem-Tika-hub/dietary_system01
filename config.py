# ============================================================
#  config.py — Project settings
#  Open this file and add your USDA key to .env (see .env.example)
# ============================================================

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# ── Keys ──────────────────────────────────────────────────
USDA_API_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")

# ── Paths ─────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
MODEL_DIR  = BASE_DIR / "models"
DATA_DIR.mkdir(exist_ok=True)
MODEL_DIR.mkdir(exist_ok=True)

# ── USDA API settings ─────────────────────────────────────
USDA_BASE_URL  = "https://api.nal.usda.gov/fdc/v1"
USDA_PAGE_SIZE = 50          # per search term (max 200 allowed by USDA)

# IMPORTANT: dataType must be a COMMA-SEPARATED STRING for GET requests,
# not a Python list — the API's GET parser does not reliably accept
# repeated-key array syntax the way requests.get(params=...) sends it.
USDA_DATA_TYPES = "Foundation,SR Legacy"

# ── Nutrient field mapping ────────────────────────────────
# USDA nutrient names (left) -> our column names (right)
NUTRIENTS_MAP = {
    "Energy"                      : "calories",
    "Protein"                     : "protein",
    "Carbohydrate, by difference" : "carbs",
    "Total lipid (fat)"           : "fat",
    "Fiber, total dietary"        : "fiber",
    "Sugars, total including NLEA": "sugar",
    "Sodium, Na"                  : "sodium",
    "Calcium, Ca"                 : "calcium",
    "Iron, Fe"                    : "iron",
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
    print(f"  Data dir    : {DATA_DIR}")
    print(f"  Model dir   : {MODEL_DIR}")
    print("=" * 45)
    if USDA_API_KEY in ("DEMO_KEY", "YOUR_FREE_KEY_HERE", ""):
        print("\n[!] Run: python test_usda_connection.py  to diagnose your key")