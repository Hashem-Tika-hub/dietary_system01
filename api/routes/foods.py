# ============================================================
#  api/routes/foods.py
#  GET /foods        — list/search foods with filters
#  GET /foods/{id}   — get single food details
# ============================================================

from typing import Optional, List
import pandas as pd
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException
from api.schemas import FoodItem, FoodSearchResponse

router  = APIRouter(prefix="/foods", tags=["Foods"])

# Load CSV once at import time
_CSV_PATH = Path(__file__).parent.parent.parent / "data" / "foods_clean.csv"
_foods_df: Optional[pd.DataFrame] = None


def _get_df() -> pd.DataFrame:
    global _foods_df
    if _foods_df is None:
        if not _CSV_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail="Food database not ready. Run 03_clean_data.py first."
            )
        _foods_df = pd.read_csv(_CSV_PATH, encoding="utf-8-sig")
    return _foods_df


@router.get("", response_model=FoodSearchResponse, summary="Search foods")
def list_foods(
    q:                Optional[str]   = Query(None,
        description="Search by name (partial match)"),
    category:         Optional[str]   = Query(None,
        description="Filter by category"),
    max_calories:     Optional[float] = Query(None, ge=0),
    min_protein:      Optional[float] = Query(None, ge=0),
    diabetic_friendly:Optional[bool]  = Query(None),
    low_sodium:       Optional[bool]  = Query(None),
    limit:            int             = Query(20, ge=1, le=100),
    offset:           int             = Query(0,  ge=0),
):
    """
    Search and filter the food database.

    Examples:
    - `/foods?q=chicken&max_calories=200`
    - `/foods?diabetic_friendly=true&min_protein=15`
    - `/foods?category=vegetables&limit=10`
    """
    df = _get_df().copy()

    # Apply filters
    if q:
        df = df[df["name"].str.contains(q, case=False, na=False)]
    if category:
        df = df[df["category"].str.contains(category, case=False, na=False)]
    if max_calories is not None:
        df = df[df["calories"] <= max_calories]
    if min_protein is not None:
        df = df[df["protein"] >= min_protein]
    if diabetic_friendly is not None and "diabetic_friendly" in df.columns:
        df = df[df["diabetic_friendly"] == diabetic_friendly]
    if low_sodium is not None and "low_sodium" in df.columns:
        df = df[df["low_sodium"] == low_sodium]

    total = len(df)
    page  = df.iloc[offset: offset + limit]

    foods = []
    for _, row in page.iterrows():
        foods.append(FoodItem(
            fdc_id           = str(row.get("fdc_id", "")),
            name             = str(row.get("name", "")),
            category         = str(row.get("category", "")),
            source           = str(row.get("source", "")),
            calories         = float(row.get("calories", 0)),
            protein          = float(row.get("protein", 0)),
            carbs            = float(row.get("carbs", 0)),
            fat              = float(row.get("fat", 0)),
            fiber            = float(row.get("fiber", 0)),
            health_score     = float(row.get("health_score", 0)),
            diabetic_friendly= bool(row.get("diabetic_friendly", False)),
            low_sodium       = bool(row.get("low_sodium", False)),
        ))

    return FoodSearchResponse(total=total, foods=foods)


@router.get("/{food_id}", response_model=FoodItem, summary="Get food by ID")
def get_food(food_id: str):
    """Get detailed nutritional info for a single food item."""
    df  = _get_df()
    row = df[df["fdc_id"].astype(str) == food_id]

    if row.empty:
        raise HTTPException(status_code=404,
                            detail=f"Food '{food_id}' not found")

    r = row.iloc[0]
    return FoodItem(
        fdc_id           = str(r.get("fdc_id", "")),
        name             = str(r.get("name", "")),
        category         = str(r.get("category", "")),
        source           = str(r.get("source", "")),
        calories         = float(r.get("calories", 0)),
        protein          = float(r.get("protein", 0)),
        carbs            = float(r.get("carbs", 0)),
        fat              = float(r.get("fat", 0)),
        fiber            = float(r.get("fiber", 0)),
        health_score     = float(r.get("health_score", 0)),
        diabetic_friendly= bool(r.get("diabetic_friendly", False)),
        low_sodium       = bool(r.get("low_sodium", False)),
    )