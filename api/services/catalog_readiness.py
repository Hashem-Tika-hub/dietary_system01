"""Catalog readiness metrics and reference allergen definitions.

This module distinguishes catalog availability from allergy-evidence completeness.
It never infers an allergen relationship from a food name, category, or nutrient
profile; only reviewed FoodAllergen or IngredientAllergen records are evidence.
"""

from __future__ import annotations

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from api.db_models import Allergen, Food, FoodAllergen, FoodNutrient


REFERENCE_ALLERGENS: tuple[tuple[str, str, str], ...] = (
    ("allergen.milk", "الحليب", "Milk"),
    ("allergen.egg", "البيض", "Egg"),
    ("allergen.wheat", "القمح", "Wheat"),
    ("allergen.gluten", "الغلوتين", "Gluten"),
    ("allergen.peanut", "الفول السوداني", "Peanut"),
    ("allergen.tree_nuts", "المكسرات الشجرية", "Tree nuts"),
    ("allergen.nuts", "المكسرات", "Nuts"),
)

REQUIRED_NUTRIENTS = frozenset({"energy_kcal", "protein_g", "carbs_g", "fat_g"})


def ensure_reference_allergens(db: Session) -> int:
    """Upsert canonical allergen reference values; return newly created count."""
    existing = {
        code
        for (code,) in db.query(Allergen.code)
        .filter(Allergen.code.in_([item[0] for item in REFERENCE_ALLERGENS]))
        .all()
    }
    created = 0
    for code, display_name_ar, display_name_en in REFERENCE_ALLERGENS:
        if code in existing:
            continue
        db.add(
            Allergen(
                code=code,
                display_name_ar=display_name_ar,
                display_name_en=display_name_en,
                description="مرجع تصنيف الحساسية؛ لا يمثل إثباتًا لعلاقة طعام محدد بها.",
            )
        )
        created += 1
    db.flush()
    return created


def catalog_readiness(db: Session) -> dict[str, int | bool | str]:
    """Return explicit availability and evidence-completeness metrics."""
    active_foods = db.query(Food.id).filter(Food.is_active.is_(True)).subquery()
    active_count = db.query(func.count()).select_from(active_foods).scalar() or 0

    nutrient_rows = (
        db.query(
            FoodNutrient.food_id,
            func.count(distinct(FoodNutrient.nutrient_code)).label("nutrient_count"),
        )
        .filter(FoodNutrient.nutrient_code.in_(REQUIRED_NUTRIENTS))
        .group_by(FoodNutrient.food_id)
        .subquery()
    )
    nutrient_complete_count = (
        db.query(func.count())
        .select_from(Food)
        .join(nutrient_rows, nutrient_rows.c.food_id == Food.id)
        .filter(
            Food.is_active.is_(True),
            nutrient_rows.c.nutrient_count == len(REQUIRED_NUTRIENTS),
        )
        .scalar()
        or 0
    )

    reference_codes = tuple(code for code, _, _ in REFERENCE_ALLERGENS)
    reference_codes_count = (
        db.query(func.count())
        .select_from(Allergen)
        .filter(Allergen.code.in_(reference_codes))
        .scalar()
        or 0
    )
    evidence_counts = (
        db.query(
            FoodAllergen.food_id,
            func.count(distinct(FoodAllergen.allergen_id)).label("allergen_count"),
        )
        .join(Allergen, Allergen.id == FoodAllergen.allergen_id)
        .filter(Allergen.code.in_(reference_codes))
        .group_by(FoodAllergen.food_id)
        .subquery()
    )
    reviewed_evidence_counts = (
        db.query(
            FoodAllergen.food_id,
            func.count(distinct(FoodAllergen.allergen_id)).label("allergen_count"),
        )
        .join(Allergen, Allergen.id == FoodAllergen.allergen_id)
        .filter(
            Allergen.code.in_(reference_codes),
            FoodAllergen.status.in_(("present", "absent")),
        )
        .group_by(FoodAllergen.food_id)
        .subquery()
    )
    unknown_evidence_foods = (
        db.query(func.count(distinct(FoodAllergen.food_id)))
        .join(Food, Food.id == FoodAllergen.food_id)
        .join(Allergen, Allergen.id == FoodAllergen.allergen_id)
        .filter(
            Food.is_active.is_(True),
            Allergen.code.in_(reference_codes),
            FoodAllergen.status == "unknown",
        )
        .scalar()
        or 0
    )
    foods_with_any_evidence = (
        db.query(func.count())
        .select_from(Food)
        .join(evidence_counts, evidence_counts.c.food_id == Food.id)
        .filter(Food.is_active.is_(True))
        .scalar()
        or 0
    )
    foods_with_complete_reference_evidence = (
        db.query(func.count())
        .select_from(Food)
        .join(reviewed_evidence_counts, reviewed_evidence_counts.c.food_id == Food.id)
        .filter(
            Food.is_active.is_(True),
            reviewed_evidence_counts.c.allergen_count == reference_codes_count,
        )
        .scalar()
        or 0
    ) if reference_codes_count else 0

    catalog_loaded = active_count > 0 and nutrient_complete_count == active_count
    allergy_evidence_complete = (
        active_count > 0
        and reference_codes_count > 0
        and foods_with_complete_reference_evidence == active_count
    )
    return {
        "active_foods": int(active_count),
        "foods_with_required_nutrients": int(nutrient_complete_count),
        "foods_missing_required_nutrients": int(active_count - nutrient_complete_count),
        "reference_allergens": int(reference_codes_count),
        "foods_with_any_allergen_evidence": int(foods_with_any_evidence),
        "foods_missing_allergen_evidence": int(active_count - foods_with_any_evidence),
        "foods_with_unknown_allergen_evidence": int(unknown_evidence_foods),
        "foods_with_complete_reference_allergen_evidence": int(
            foods_with_complete_reference_evidence
        ),
        "catalog_loaded": catalog_loaded,
        "allergy_evidence_complete": allergy_evidence_complete,
        "status": (
            "ready" if catalog_loaded and allergy_evidence_complete
            else "catalog_ready_allergy_evidence_incomplete" if catalog_loaded
            else "catalog_incomplete"
        ),
    }
