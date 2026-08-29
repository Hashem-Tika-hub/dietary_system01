"""Add normalized food, meal, preference, and interaction architecture.

Revision ID: e7f1a2b3c4d5
Revises: d1e4c73a0f11
Create Date: 2026-08-29 12:00:00.000000
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d1e4c73a0f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORIES = (
    ("protein", "بروتين", "Protein"),
    ("vegetables", "خضروات", "Vegetables"),
    ("fruits", "فواكه", "Fruits"),
    ("grains", "حبوب ونشويات", "Grains"),
    ("dairy", "ألبان", "Dairy"),
    ("legumes", "بقوليات", "Legumes"),
    ("nuts", "مكسرات وبذور", "Nuts and seeds"),
    ("oils", "زيوت ودهون", "Oils and fats"),
    ("beverages", "مشروبات", "Beverages"),
    ("snacks", "وجبات خفيفة وحلويات", "Snacks and sweets"),
    ("other", "أخرى", "Other"),
)

MEAL_TYPES = (
    ("breakfast", "فطور", "Breakfast"),
    ("lunch", "غداء", "Lunch"),
    ("dinner", "عشاء", "Dinner"),
    ("snack", "سناك", "Snack"),
)

TAGS = (
    ("high_protein", "عالي البروتين", "High protein"),
    ("low_sodium", "منخفض الصوديوم", "Low sodium"),
    ("diabetes_friendly", "ملائم للسكري حسب قواعد النظام", "Diabetes-friendly by system rules"),
    ("vegetarian", "نباتي", "Vegetarian"),
    ("vegan", "نباتي صرف", "Vegan"),
    ("low_carb", "منخفض الكربوهيدرات", "Low carb"),
    ("gluten_free", "خالٍ من الغلوتين", "Gluten-free"),
    ("lactose_free", "خالٍ من اللاكتوز", "Lactose-free"),
)


def _category_code(value: str | None) -> str:
    text = (value or "").strip()
    if any(token in text for token in ("خضر", "سلط")):
        return "vegetables"
    if "فواك" in text:
        return "fruits"
    if any(token in text for token in ("حبوب", "أرز", "مكرونة", "مخبوز", "معجن")):
        return "grains"
    if "ألبان" in text:
        return "dairy"
    if "بقول" in text:
        return "legumes"
    if any(token in text for token in ("مكسر", "بذور")):
        return "nuts"
    if any(token in text for token in ("أسماك", "سمك", "دواجن", "لحوم", "بيض")):
        return "protein"
    if any(token in text for token in ("زيوت", "دهون")):
        return "oils"
    if "مشروبات" in text:
        return "beverages"
    if any(token in text for token in ("سناك", "حلويات", "سكريات", "مقبلات", "صلصات", "شوربات", "يخنات", "أطباق")):
        return "snacks"
    return "other"


def _meal_codes(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [part.strip() for part in value.split("،")]
    if not isinstance(value, list):
        return []
    codes: list[str] = []
    for item in value:
        text = str(item).strip()
        if text == "فطور":
            codes.append("breakfast")
        elif text == "غداء":
            codes.append("lunch")
        elif text == "عشاء":
            codes.append("dinner")
        elif text in {"سناك", "حلوى"}:
            codes.append("snack")
    return list(dict.fromkeys(codes))


def _create_tables() -> None:
    op.create_table(
        "food_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("display_name_ar", sa.String(100), nullable=False),
        sa.Column("display_name_en", sa.String(100)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_food_categories_code"),
    )
    op.create_index("ix_food_categories_code", "food_categories", ["code"], unique=False)

    op.create_table(
        "dietary_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("display_name_ar", sa.String(100), nullable=False),
        sa.Column("display_name_en", sa.String(100)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_dietary_tags_code"),
    )
    op.create_index("ix_dietary_tags_code", "dietary_tags", ["code"], unique=False)

    op.create_table(
        "meal_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("display_name_ar", sa.String(100), nullable=False),
        sa.Column("display_name_en", sa.String(100)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_meal_types_code"),
    )
    op.create_index("ix_meal_types_code", "meal_types", ["code"], unique=False)

    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("name <> ''", name="ck_meals_name_nonempty"),
    )
    op.create_index("ix_meals_name", "meals", ["name"], unique=False)
    op.create_index("ix_meals_is_active", "meals", ["is_active"], unique=False)

    op.create_table(
        "food_dietary_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("dietary_tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("catalog_sources.id")),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="estimated"),
        sa.UniqueConstraint("food_id", "tag_id", name="uq_food_dietary_tag"),
    )
    op.create_index("ix_food_dietary_tags_food_id", "food_dietary_tags", ["food_id"], unique=False)
    op.create_index("ix_food_dietary_tags_tag_id", "food_dietary_tags", ["tag_id"], unique=False)

    op.create_table(
        "food_meal_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meal_type_id", sa.Integer(), sa.ForeignKey("meal_types.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("food_id", "meal_type_id", name="uq_food_meal_type"),
    )
    op.create_index("ix_food_meal_types_food_id", "food_meal_types", ["food_id"], unique=False)
    op.create_index("ix_food_meal_types_meal_type_id", "food_meal_types", ["meal_type_id"], unique=False)

    op.create_table(
        "meal_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meal_id", sa.Integer(), sa.ForeignKey("meals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id"), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False, server_default="g"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("meal_id", "food_id", "position", name="uq_meal_ingredient_position"),
        sa.CheckConstraint("quantity > 0", name="ck_meal_ingredient_quantity_positive"),
        sa.CheckConstraint("unit IN ('g', 'ml', 'piece', 'serving')", name="ck_meal_ingredient_unit_allowed"),
        sa.CheckConstraint("position >= 0", name="ck_meal_ingredient_position_nonnegative"),
    )
    op.create_index("ix_meal_ingredients_meal_id", "meal_ingredients", ["meal_id"], unique=False)
    op.create_index("ix_meal_ingredients_food_id", "meal_ingredients", ["food_id"], unique=False)

    op.create_table(
        "meal_meal_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meal_id", sa.Integer(), sa.ForeignKey("meals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meal_type_id", sa.Integer(), sa.ForeignKey("meal_types.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("meal_id", "meal_type_id", name="uq_meal_meal_type"),
    )
    op.create_index("ix_meal_meal_types_meal_id", "meal_meal_types", ["meal_id"], unique=False)
    op.create_index("ix_meal_meal_types_meal_type_id", "meal_meal_types", ["meal_type_id"], unique=False)

    op.create_table(
        "user_food_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preference_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "food_id", name="uq_user_food_preference"),
        sa.CheckConstraint("preference_type IN ('favorite', 'dislike', 'exclude')", name="ck_user_food_preference_type_allowed"),
    )
    op.create_index("ix_user_food_preferences_user_id", "user_food_preferences", ["user_id"], unique=False)
    op.create_index("ix_user_food_preferences_food_id", "user_food_preferences", ["food_id"], unique=False)

    op.create_table(
        "user_dietary_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("dietary_tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "tag_id", name="uq_user_dietary_preference"),
    )
    op.create_index("ix_user_dietary_preferences_user_id", "user_dietary_preferences", ["user_id"], unique=False)
    op.create_index("ix_user_dietary_preferences_tag_id", "user_dietary_preferences", ["tag_id"], unique=False)

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id", ondelete="SET NULL")),
        sa.Column("meal_id", sa.Integer(), sa.ForeignKey("meals.id", ondelete="SET NULL")),
        sa.Column("recommendation_source", sa.String(20), nullable=False),
        sa.Column("recommendation_score", sa.Float()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("food_id IS NOT NULL OR meal_id IS NOT NULL", name="ck_recommendation_target_required"),
        sa.CheckConstraint("recommendation_source IN ('CBF', 'CF', 'HYBRID', 'RULE_BASED')", name="ck_recommendation_source_allowed"),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"], unique=False)
    op.create_index("ix_recommendations_food_id", "recommendations", ["food_id"], unique=False)
    op.create_index("ix_recommendations_meal_id", "recommendations", ["meal_id"], unique=False)
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"], unique=False)

    op.create_table(
        "user_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id", ondelete="SET NULL")),
        sa.Column("meal_id", sa.Integer(), sa.ForeignKey("meals.id", ondelete="SET NULL")),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendations.id", ondelete="SET NULL")),
        sa.Column("interaction_type", sa.String(20), nullable=False),
        sa.Column("rating", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("food_id IS NOT NULL OR meal_id IS NOT NULL", name="ck_interaction_target_required"),
        sa.CheckConstraint("interaction_type IN ('VIEW', 'ACCEPT', 'REJECT', 'SWAP', 'FAVORITE', 'CONSUMED', 'RATE')", name="ck_interaction_type_allowed"),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_interaction_rating_range"),
    )
    op.create_index("ix_user_interactions_user_id", "user_interactions", ["user_id"], unique=False)
    op.create_index("ix_user_interactions_food_id", "user_interactions", ["food_id"], unique=False)
    op.create_index("ix_user_interactions_meal_id", "user_interactions", ["meal_id"], unique=False)
    op.create_index("ix_user_interactions_recommendation_id", "user_interactions", ["recommendation_id"], unique=False)
    op.create_index("ix_user_interactions_created_at", "user_interactions", ["created_at"], unique=False)


def _seed_dimensions(connection: sa.Connection) -> None:
    connection.execute(
        sa.insert(
            sa.table("food_categories", sa.column("code"), sa.column("display_name_ar"), sa.column("display_name_en"))
        ),
        [dict(code=code, display_name_ar=ar, display_name_en=en) for code, ar, en in CATEGORIES],
    )
    connection.execute(
        sa.insert(
            sa.table("dietary_tags", sa.column("code"), sa.column("display_name_ar"), sa.column("display_name_en"))
        ),
        [dict(code=code, display_name_ar=ar, display_name_en=en) for code, ar, en in TAGS],
    )
    connection.execute(
        sa.insert(
            sa.table("meal_types", sa.column("code"), sa.column("display_name_ar"), sa.column("display_name_en"))
        ),
        [dict(code=code, display_name_ar=ar, display_name_en=en) for code, ar, en in MEAL_TYPES],
    )


def _backfill_food_dimensions(connection: sa.Connection) -> None:
    connection.execute(sa.text("ALTER TABLE foods ADD COLUMN category_id INTEGER REFERENCES food_categories(id)"))
    category_ids = {
        row.code: row.id
        for row in connection.execute(sa.text("SELECT id, code FROM food_categories"))
    }
    tag_ids = {
        row.code: row.id
        for row in connection.execute(sa.text("SELECT id, code FROM dietary_tags"))
    }
    meal_type_ids = {
        row.code: row.id
        for row in connection.execute(sa.text("SELECT id, code FROM meal_types"))
    }
    foods = connection.execute(sa.text("SELECT id, category, meal_tags, is_high_protein, low_sodium, diabetic_friendly FROM foods")).mappings()
    for food in foods:
        category_id = category_ids[_category_code(food["category"])]
        connection.execute(
            sa.text("UPDATE foods SET category_id = :category_id WHERE id = :food_id"),
            {"category_id": category_id, "food_id": food["id"]},
        )
        for meal_code in _meal_codes(food["meal_tags"]):
            connection.execute(
                sa.text("INSERT INTO food_meal_types (food_id, meal_type_id) VALUES (:food_id, :meal_type_id)"),
                {"food_id": food["id"], "meal_type_id": meal_type_ids[meal_code]},
            )
        flags = {
            "high_protein": food["is_high_protein"],
            "low_sodium": food["low_sodium"],
            "diabetes_friendly": food["diabetic_friendly"],
        }
        for tag_code, enabled in flags.items():
            if enabled:
                connection.execute(
                    sa.text("INSERT INTO food_dietary_tags (food_id, tag_id, data_quality) VALUES (:food_id, :tag_id, 'estimated')"),
                    {"food_id": food["id"], "tag_id": tag_ids[tag_code]},
                )


def upgrade() -> None:
    _create_tables()
    connection = op.get_bind()
    _seed_dimensions(connection)
    _backfill_food_dimensions(connection)


def downgrade() -> None:
    op.drop_table("user_interactions")
    op.drop_table("recommendations")
    op.drop_table("user_dietary_preferences")
    op.drop_table("user_food_preferences")
    op.drop_index("ix_meal_meal_types_meal_type_id", table_name="meal_meal_types")
    op.drop_index("ix_meal_meal_types_meal_id", table_name="meal_meal_types")
    op.drop_table("meal_meal_types")
    op.drop_index("ix_meal_ingredients_food_id", table_name="meal_ingredients")
    op.drop_index("ix_meal_ingredients_meal_id", table_name="meal_ingredients")
    op.drop_table("meal_ingredients")
    op.drop_index("ix_food_meal_types_meal_type_id", table_name="food_meal_types")
    op.drop_index("ix_food_meal_types_food_id", table_name="food_meal_types")
    op.drop_table("food_meal_types")
    op.drop_index("ix_food_dietary_tags_tag_id", table_name="food_dietary_tags")
    op.drop_index("ix_food_dietary_tags_food_id", table_name="food_dietary_tags")
    op.drop_table("food_dietary_tags")
    op.drop_index("ix_meals_is_active", table_name="meals")
    op.drop_index("ix_meals_name", table_name="meals")
    op.drop_table("meals")
    op.drop_index("ix_meal_types_code", table_name="meal_types")
    op.drop_table("meal_types")
    with op.batch_alter_table("foods") as batch_op:
        batch_op.drop_column("category_id")
    op.drop_index("ix_dietary_tags_code", table_name="dietary_tags")
    op.drop_table("dietary_tags")
    op.drop_index("ix_food_categories_code", table_name="food_categories")
    op.drop_table("food_categories")
