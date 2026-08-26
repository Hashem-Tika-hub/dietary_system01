"""Food catalog search backed by the relational catalog database."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload

from api.database import get_db
from api.db_models import Food
from api.schemas import CatalogReadinessResponse, FoodItem, FoodSearchResponse
from api.services.catalog_readiness import catalog_readiness


router = APIRouter(prefix="/foods", tags=["Foods"])

_NUTRIENT_CODES = {
    "calories": "energy_kcal",
    "protein": "protein_g",
    "carbs": "carbs_g",
    "fat": "fat_g",
    "fiber": "fiber_g",
}


def _food_item(food: Food) -> FoodItem:
    nutrients = {nutrient.nutrient_code: nutrient.amount for nutrient in food.nutrients}
    return FoodItem(
        fdc_id=str(food.external_id),
        name=food.display_name,
        category=food.category or "",
        food_group=food.food_group or "",
        meal_type="، ".join(food.meal_tags or []),
        source=food.source.name if food.source else "",
        calories=float(nutrients.get(_NUTRIENT_CODES["calories"], 0.0)),
        protein=float(nutrients.get(_NUTRIENT_CODES["protein"], 0.0)),
        carbs=float(nutrients.get(_NUTRIENT_CODES["carbs"], 0.0)),
        fat=float(nutrients.get(_NUTRIENT_CODES["fat"], 0.0)),
        fiber=float(nutrients.get(_NUTRIENT_CODES["fiber"], 0.0)),
        health_score=float(food.health_score),
        diabetic_friendly=bool(food.diabetic_friendly),
        low_sodium=bool(food.low_sodium),
    )


def _catalog_query(db: Session):
    return (
        db.query(Food)
        .options(joinedload(Food.source), selectinload(Food.nutrients))
        .filter(Food.is_active.is_(True))
    )


def _ensure_catalog_has_foods(db: Session) -> None:
    if not db.query(Food.id).filter(Food.is_active.is_(True)).first():
        raise HTTPException(
            status_code=503,
            detail=(
                "كتالوج الطعام غير مستورد بعد. نفّذ الترحيلات ثم استورد "
                "مصدر الكتالوج الموثق قبل استخدام البحث أو التوصيات."
            ),
        )


@router.get("", response_model=FoodSearchResponse, summary="Search foods")
def list_foods(
    q: Optional[str] = Query(None, description="Search by name (partial match)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    max_calories: Optional[float] = Query(None, ge=0),
    min_protein: Optional[float] = Query(None, ge=0),
    diabetic_friendly: Optional[bool] = Query(None),
    low_sodium: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Search the catalog database, never an in-memory CSV snapshot."""
    _ensure_catalog_has_foods(db)
    query = _catalog_query(db)
    if q:
        query = query.filter(Food.display_name.ilike(f"%{q.strip()}%"))
    if category:
        query = query.filter(Food.category.ilike(f"%{category.strip()}%"))
    if diabetic_friendly is not None:
        query = query.filter(Food.diabetic_friendly.is_(diabetic_friendly))
    if low_sodium is not None:
        query = query.filter(Food.low_sodium.is_(low_sodium))

    # Nutrient values are normalized in FoodNutrient and loaded in one batch.
    # The curated catalog is deliberately small enough for deterministic
    # in-service filtering; database pagination still happens after filtering.
    foods = [_food_item(food) for food in query.order_by(Food.id).all()]
    if max_calories is not None:
        foods = [food for food in foods if food.calories <= max_calories]
    if min_protein is not None:
        foods = [food for food in foods if food.protein >= min_protein]

    total = len(foods)
    return FoodSearchResponse(total=total, foods=foods[offset: offset + limit])


@router.get("/readiness", response_model=CatalogReadinessResponse, summary="Get catalog readiness")
def get_catalog_readiness(db: Session = Depends(get_db)):
    """Expose measured catalog availability and allergen-evidence completeness."""
    return catalog_readiness(db)


@router.get("/{food_id}", response_model=FoodItem, summary="Get food by ID")
def get_food(food_id: str, db: Session = Depends(get_db)):
    """Get a single active catalog item by its stable external identifier."""
    _ensure_catalog_has_foods(db)
    food = (
        _catalog_query(db)
        .filter(Food.external_id == str(food_id))
        .one_or_none()
    )
    if food is None:
        raise HTTPException(status_code=404, detail=f"Food '{food_id}' not found")
    return _food_item(food)
