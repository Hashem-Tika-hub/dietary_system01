"""Integration tests for food catalog and allergen traceability migrations."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_COMMAND = [sys.executable, "-m", "alembic"]
CATALOG_TABLES = {
    "catalog_sources",
    "foods",
    "food_nutrients",
    "food_portions",
    "ingredients",
    "food_ingredients",
    "allergens",
    "ingredient_allergens",
    "food_allergens",
}


def run_alembic(*arguments: str, database_url: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [*ALEMBIC_COMMAND, *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def reflect_catalog(database_url: str):
    engine = create_engine(database_url)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return engine, metadata


def test_catalog_migration_creates_all_traceability_tables(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'catalog.db'}"
    run_alembic("upgrade", "head", database_url=database_url)

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert CATALOG_TABLES <= set(inspector.get_table_names())
        assert {
            "ix_food_allergens_food_id",
            "ix_food_allergens_allergen_id",
        } <= {index["name"] for index in inspector.get_indexes("food_allergens")}
        assert "ix_ingredient_allergens_allergen_id" in {
            index["name"] for index in inspector.get_indexes("ingredient_allergens")
        }
    finally:
        engine.dispose()


def test_catalog_preserves_source_nutrient_ingredient_and_allergen_links(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'linked-catalog.db'}"
    run_alembic("upgrade", "head", database_url=database_url)
    engine, metadata = reflect_catalog(database_url)
    now = datetime.now(UTC)

    try:
        with engine.begin() as connection:
            source_id = connection.execute(
                metadata.tables["catalog_sources"].insert().values(
                    code="test-source-v1",
                    name="Test source",
                    version="1.0",
                    imported_at=now,
                )
            ).inserted_primary_key[0]
            food_id = connection.execute(
                metadata.tables["foods"].insert().values(
                    source_id=source_id,
                    external_id="FOOD-001",
                    display_name="وجبة اختبار",
                    food_kind="recipe",
                    meal_tags=["lunch"],
                    basis_grams=100.0,
                    data_quality="verified",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            ).inserted_primary_key[0]
            ingredient_id = connection.execute(
                metadata.tables["ingredients"].insert().values(
                    canonical_name="milk",
                    display_name_ar="حليب",
                )
            ).inserted_primary_key[0]
            allergen_id = connection.execute(
                metadata.tables["allergens"].insert().values(
                    code="allergen.milk",
                    display_name_ar="الحليب",
                    display_name_en="Milk",
                )
            ).inserted_primary_key[0]
            connection.execute(
                metadata.tables["food_nutrients"].insert().values(
                    food_id=food_id,
                    nutrient_code="energy_kcal",
                    amount=160.0,
                    unit="kcal",
                    basis_grams=100.0,
                    data_quality="verified",
                )
            )
            connection.execute(
                metadata.tables["food_portions"].insert().values(
                    food_id=food_id,
                    label="حصة اختبار",
                    grams=150.0,
                    is_default=True,
                )
            )
            connection.execute(
                metadata.tables["food_ingredients"].insert().values(
                    food_id=food_id,
                    ingredient_id=ingredient_id,
                    amount_g=120.0,
                    role="primary",
                    is_optional=False,
                )
            )
            connection.execute(
                metadata.tables["ingredient_allergens"].insert().values(
                    ingredient_id=ingredient_id,
                    allergen_id=allergen_id,
                    status="present",
                    source_id=source_id,
                    reviewed_at=now,
                )
            )
            connection.execute(
                metadata.tables["food_allergens"].insert().values(
                    food_id=food_id,
                    allergen_id=allergen_id,
                    status="present",
                    source_id=source_id,
                    is_derived=True,
                    reviewed_at=now,
                )
            )

        with engine.connect() as connection:
            result = connection.execute(
                metadata.tables["food_allergens"].select()
            ).mappings().one()
        assert result["status"] == "present"
        assert result["is_derived"] is True

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    metadata.tables["food_allergens"].insert().values(
                        food_id=food_id,
                        allergen_id=allergen_id,
                        status="present",
                        is_derived=False,
                    )
                )
    finally:
        engine.dispose()


def test_catalog_rejects_nonpositive_portion_weight(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'invalid-portion.db'}"
    run_alembic("upgrade", "head", database_url=database_url)
    engine, metadata = reflect_catalog(database_url)
    now = datetime.now(UTC)

    try:
        with engine.begin() as connection:
            source_id = connection.execute(
                metadata.tables["catalog_sources"].insert().values(
                    code="test-invalid-portion-source",
                    name="Test source",
                    version="1.0",
                    imported_at=now,
                )
            ).inserted_primary_key[0]
            food_id = connection.execute(
                metadata.tables["foods"].insert().values(
                    source_id=source_id,
                    external_id="FOOD-INVALID-PORTION",
                    display_name="طعام اختبار",
                    food_kind="food",
                    meal_tags=["dinner"],
                    basis_grams=100.0,
                    data_quality="verified",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            ).inserted_primary_key[0]

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    metadata.tables["food_portions"].insert().values(
                        food_id=food_id,
                        label="حصة غير صالحة",
                        grams=0.0,
                        is_default=True,
                    )
                )
    finally:
        engine.dispose()


def test_catalog_rejects_unknown_nutrient_data_quality(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'invalid-nutrient-quality.db'}"
    run_alembic("upgrade", "head", database_url=database_url)
    engine, metadata = reflect_catalog(database_url)
    now = datetime.now(UTC)

    try:
        with engine.begin() as connection:
            source_id = connection.execute(
                metadata.tables["catalog_sources"].insert().values(
                    code="test-invalid-nutrient-source",
                    name="Test source",
                    version="1.0",
                    imported_at=now,
                )
            ).inserted_primary_key[0]
            food_id = connection.execute(
                metadata.tables["foods"].insert().values(
                    source_id=source_id,
                    external_id="FOOD-INVALID-NUTRIENT-QUALITY",
                    display_name="طعام اختبار",
                    food_kind="food",
                    meal_tags=["breakfast"],
                    basis_grams=100.0,
                    data_quality="verified",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            ).inserted_primary_key[0]

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    metadata.tables["food_nutrients"].insert().values(
                        food_id=food_id,
                        nutrient_code="protein_g",
                        amount=10.0,
                        unit="g",
                        basis_grams=100.0,
                        data_quality="unverified",
                    )
                )
    finally:
        engine.dispose()
