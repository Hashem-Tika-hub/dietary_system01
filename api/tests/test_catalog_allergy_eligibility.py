from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base
from api.db_models import (
    Allergen,
    CatalogSource,
    Food,
    FoodAllergen,
    FoodIngredient,
    Ingredient,
    IngredientAllergen,
)
from api.services.allergen_eligibility import (
    BLOCKED,
    ELIGIBLE,
    UNKNOWN_METADATA,
    evaluate_catalog_allergy_eligibility,
)


@pytest.fixture()
def catalog_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog-allergy.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    source = CatalogSource(code="fixture", name="Fixture", version="1")
    allergen = Allergen(code="allergen.milk", display_name_ar="الحليب")
    session.add_all([source, allergen])
    session.flush()

    safe = Food(source_id=source.id, external_id="safe", display_name="آمن")
    direct_conflict = Food(
        source_id=source.id,
        external_id="direct-conflict",
        display_name="حليب مباشر",
    )
    ingredient_conflict = Food(
        source_id=source.id,
        external_id="ingredient-conflict",
        display_name="وصفة بمكوّن حليب",
    )
    unknown = Food(source_id=source.id, external_id="unknown", display_name="بيانات ناقصة")
    ingredient = Ingredient(canonical_name="milk", display_name_ar="حليب")
    session.add_all([safe, direct_conflict, ingredient_conflict, unknown, ingredient])
    session.flush()
    session.add_all([
        FoodAllergen(
            food_id=safe.id,
            allergen_id=allergen.id,
            status="absent",
            source_id=source.id,
            reviewed_at=datetime.utcnow(),
        ),
        FoodAllergen(
            food_id=direct_conflict.id,
            allergen_id=allergen.id,
            status="present",
            source_id=source.id,
            reviewed_at=datetime.utcnow(),
        ),
        FoodIngredient(food_id=ingredient_conflict.id, ingredient_id=ingredient.id),
        IngredientAllergen(
            ingredient_id=ingredient.id,
            allergen_id=allergen.id,
            status="present",
            source_id=source.id,
            reviewed_at=datetime.utcnow(),
        ),
    ])
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_catalog_evidence_blocks_food_and_ingredient_conflicts(catalog_db: Session) -> None:
    decisions = evaluate_catalog_allergy_eligibility(
        catalog_db,
        ["safe", "direct-conflict", "ingredient-conflict", "unknown"],
        ["حليب"],
    )

    assert decisions["safe"].status == ELIGIBLE
    assert decisions["direct-conflict"].status == BLOCKED
    assert decisions["direct-conflict"].blocked_codes == ("allergen.milk",)
    assert decisions["ingredient-conflict"].status == BLOCKED
    assert decisions["ingredient-conflict"].blocked_codes == ("allergen.milk",)
    assert decisions["unknown"].status == UNKNOWN_METADATA
    assert decisions["unknown"].unknown_codes == ("allergen.milk",)


def test_explicit_food_absence_is_not_overridden_when_ingredient_evidence_is_missing(catalog_db: Session) -> None:
    decisions = evaluate_catalog_allergy_eligibility(catalog_db, ["safe"], ["allergen.milk"])

    assert decisions["safe"].status == ELIGIBLE


def test_no_declared_allergy_keeps_catalog_candidates_eligible(catalog_db: Session) -> None:
    decisions = evaluate_catalog_allergy_eligibility(
        catalog_db,
        ["safe", "direct-conflict", "unknown"],
        [],
    )

    assert {key: decision.status for key, decision in decisions.items()} == {
        "safe": ELIGIBLE,
        "direct-conflict": ELIGIBLE,
        "unknown": ELIGIBLE,
    }
