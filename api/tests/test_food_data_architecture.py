from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_alembic(*arguments: str, database_url: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_normalized_schema_is_created_and_backfills_existing_food_dimensions(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'food-architecture.db'}"
    run_alembic("upgrade", "d1e4c73a0f11", database_url=database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            source_id = connection.execute(
                text(
                    """
                    INSERT INTO catalog_sources (code, name, version, imported_at)
                    VALUES ('test-source', 'Test source', '1', CURRENT_TIMESTAMP)
                    RETURNING id
                    """
                )
            ).scalar_one()
            food_id = connection.execute(
                text(
                    """
                    INSERT INTO foods (
                        source_id, external_id, display_name, food_kind, category,
                        food_group, meal_tags, basis_grams, data_quality, health_score,
                        diabetic_friendly, low_sodium, is_high_protein, is_active,
                        created_at, updated_at
                    ) VALUES (
                        :source_id, 'TEST-1', 'اختبار أرز', 'food', 'أطباق أرز',
                        'نشويات', '["غداء", "عشاء"]', 100, 'estimated', 50,
                        1, 1, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    ) RETURNING id
                    """
                ),
                {"source_id": source_id},
            ).scalar_one()
        run_alembic("upgrade", "head", database_url=database_url)
        with engine.connect() as connection:
            tables = set(inspect(engine).get_table_names())
            assert {
                "food_categories",
                "dietary_tags",
                "food_dietary_tags",
                "meal_types",
                "food_meal_types",
                "meals",
                "meal_ingredients",
                "user_food_preferences",
                "user_dietary_preferences",
                "recommendations",
                "user_interactions",
            } <= tables
            category = connection.execute(
                text("SELECT code FROM food_categories JOIN foods ON foods.category_id = food_categories.id WHERE foods.id = :id"),
                {"id": food_id},
            ).scalar_one()
            assert category == "grains"
            meal_codes = set(
                connection.execute(
                    text(
                        """
                        SELECT meal_types.code
                        FROM food_meal_types
                        JOIN meal_types ON meal_types.id = food_meal_types.meal_type_id
                        WHERE food_meal_types.food_id = :food_id
                        """
                    ),
                    {"food_id": food_id},
                ).scalars()
            )
            assert meal_codes == {"lunch", "dinner"}
            tag_codes = set(
                connection.execute(
                    text(
                        """
                        SELECT dietary_tags.code
                        FROM food_dietary_tags
                        JOIN dietary_tags ON dietary_tags.id = food_dietary_tags.tag_id
                        WHERE food_dietary_tags.food_id = :food_id
                        """
                    ),
                    {"food_id": food_id},
                ).scalars()
            )
            assert tag_codes == {"low_sodium", "diabetes_friendly"}
    finally:
        engine.dispose()


def test_preference_and_interaction_constraints_are_enforced(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'constraints.db'}"
    run_alembic("upgrade", "head", database_url=database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            source_id = connection.execute(
                text(
                    "INSERT INTO catalog_sources (code, name, version, imported_at) VALUES ('source', 'Source', '1', CURRENT_TIMESTAMP) RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO foods (
                        source_id, external_id, display_name, food_kind, meal_tags, basis_grams,
                        data_quality, health_score, diabetic_friendly, low_sodium,
                        is_high_protein, is_active, created_at, updated_at
                    ) VALUES (:source_id, 'F-1', 'Food', 'food', '[]', 100, 'estimated', 0, 0, 0, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                ),
                {"source_id": source_id},
            )
            food_id = connection.execute(text("SELECT id FROM foods WHERE external_id = 'F-1'")).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO users (email, hashed_password, name, age, gender, weight, height, activity_level, goal)
                    VALUES ('architecture@example.com', 'hash', 'User', 30, 'male', 75, 175, 3, 'maintain')
                    """
                )
            )
            user_id = connection.execute(text("SELECT id FROM users WHERE email = 'architecture@example.com'")).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO user_food_preferences (user_id, food_id, preference_type, created_at)
                    VALUES (:user_id, :food_id, 'exclude', CURRENT_TIMESTAMP)
                    """
                ),
                {"user_id": user_id, "food_id": food_id},
            )
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO user_interactions (user_id, food_id, interaction_type, rating, created_at)
                        VALUES (:user_id, :food_id, 'RATE', 6, CURRENT_TIMESTAMP)
                        """
                    ),
                    {"user_id": user_id, "food_id": food_id},
                )
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO user_interactions (user_id, interaction_type, created_at)
                        VALUES (:user_id, 'VIEW', CURRENT_TIMESTAMP)
                        """
                    ),
                    {"user_id": user_id},
                )
    finally:
        engine.dispose()
