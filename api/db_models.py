# ============================================================
#  api/db_models.py — جداول قاعدة البيانات
# ============================================================

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return a UTC timestamp compatible with current naive SQLite columns."""
    return datetime.now(UTC).replace(tzinfo=None)


from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from api.database import Base


class User(Base):
    """جدول المستخدمين."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("age BETWEEN 10 AND 100", name="ck_users_age_range"),
        CheckConstraint("weight BETWEEN 30.0 AND 300.0", name="ck_users_weight_range"),
        CheckConstraint("height BETWEEN 100.0 AND 250.0", name="ck_users_height_range"),
        CheckConstraint(
            "activity_level BETWEEN 1 AND 5",
            name="ck_users_activity_level_range",
        ),
        CheckConstraint(
            "weight * 10000.0 / (height * height) BETWEEN 10.0 AND 80.0",
            name="ck_users_body_profile_bmi_sanity",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), default="مستخدم")
    created_at = Column(DateTime, default=utcnow)

    # بيانات الجسم
    age = Column(Integer, nullable=False)
    gender = Column(String(10), default="male")
    weight = Column(Float, nullable=False)  # كجم
    height = Column(Float, nullable=False)  # سم
    activity_level = Column(Integer, default=2)  # 1-5

    # الهدف والصحة
    goal = Column(String(20), default="maintain")
    has_diabetes = Column(Boolean, default=False)
    has_bp = Column(Boolean, default=False)
    has_cholesterol = Column(Boolean, default=False)
    allergies = Column(JSON, default=list)  # ستُنقل لاحقًا إلى user_constraints

    # تفضيلات الطعام التفصيلية
    dislikes = Column(JSON, default=list)
    favorites = Column(JSON, default=list)
    cuisine_style = Column(String(20), default="مزيج")
    allow_treats = Column(Boolean, default=False)

    meal_logs = relationship("MealLog", back_populates="user", cascade="all, delete")
    weekly_plans = relationship(
        "WeeklyPlan", back_populates="user", cascade="all, delete"
    )
    food_feedback = relationship(
        "UserFoodFeedback", back_populates="user", cascade="all, delete-orphan"
    )


class MealLog(Base):
    """سجل الوجبات المتناولة."""

    __tablename__ = "meal_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, default=utcnow)
    meal_type = Column(String(20))
    food_name = Column(String(255))
    fdc_id = Column(String(50))
    portion_g = Column(Float, default=100)
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat = Column(Float, default=0)
    notes = Column(Text, default="")

    user = relationship("User", back_populates="meal_logs")


class UserFoodFeedback(Base):
    """تفاعل صريح ومصرّح به بين المستخدم وصنف من كتالوج الطعام.

    يحتفظ النظام بسجل حالي واحد لكل زوج (مستخدم، طعام). ويُستخدم هذا الجدول
    فقط لتدريب التصفية التعاونية الحقيقية؛ سجلات تناول الوجبات لا تُحوَّل
    تلقائيًا إلى تفضيلات.
    """

    __tablename__ = "user_food_feedback"
    __table_args__ = (
        UniqueConstraint("user_id", "food_id", name="uq_user_food_feedback"),
        CheckConstraint(
            "event_type IN ('like', 'dislike', 'save', 'not_interested')",
            name="ck_user_food_feedback_event_type_allowed",
        ),
        CheckConstraint(
            "score IN (-1.0, 0.5, 1.0)",
            name="ck_user_food_feedback_score_allowed",
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    food_id = Column(
        Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type = Column(String(30), nullable=False)
    score = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user = relationship("User", back_populates="food_feedback")
    food = relationship("Food", back_populates="feedback_records")


class WeeklyPlan(Base):
    """الخطط الأسبوعية المُولَّدة."""

    __tablename__ = "weekly_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    plan_data = Column(JSON, nullable=False)

    user = relationship("User", back_populates="weekly_plans")


# ── كتالوج الطعام الموثق ──────────────────────────────────


class CatalogSource(Base):
    """مصدر بيانات كتالوج الطعام وإصداره القابلان للتتبع."""

    __tablename__ = "catalog_sources"

    id = Column(Integer, primary_key=True)
    code = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    version = Column(String(100), nullable=False)
    license_url = Column(String(500))
    checksum = Column(String(128))
    imported_at = Column(DateTime, nullable=False, default=utcnow)

    foods = relationship("Food", back_populates="source")
    ingredient_allergen_records = relationship(
        "IngredientAllergen", back_populates="source"
    )
    food_allergen_records = relationship("FoodAllergen", back_populates="source")


class Food(Base):
    """صنف غذائي أو وصفة ضمن كتالوج موثق المصدر."""

    __tablename__ = "foods"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_food_source_external_id"),
        CheckConstraint("basis_grams > 0", name="ck_food_basis_grams_positive"),
        CheckConstraint(
            "food_kind IN ('food', 'recipe')", name="ck_food_kind_allowed"
        ),
        CheckConstraint(
            "data_quality IN ('verified', 'estimated')",
            name="ck_food_data_quality_allowed",
        ),
    )

    id = Column(Integer, primary_key=True)
    source_id = Column(
        Integer, ForeignKey("catalog_sources.id"), nullable=False, index=True
    )
    external_id = Column(String(100), nullable=False)
    display_name = Column(String(255), nullable=False, index=True)
    food_kind = Column(String(20), nullable=False, default="food")
    category = Column(String(100))
    food_group = Column(String(100))
    meal_tags = Column(JSON, nullable=False, default=list)
    basis_grams = Column(Float, nullable=False, default=100.0)
    data_quality = Column(String(20), nullable=False, default="verified")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    source = relationship("CatalogSource", back_populates="foods")
    nutrients = relationship(
        "FoodNutrient", back_populates="food", cascade="all, delete-orphan"
    )
    portions = relationship(
        "FoodPortion", back_populates="food", cascade="all, delete-orphan"
    )
    ingredient_links = relationship(
        "FoodIngredient", back_populates="food", cascade="all, delete-orphan"
    )
    allergen_records = relationship(
        "FoodAllergen", back_populates="food", cascade="all, delete-orphan"
    )
    feedback_records = relationship(
        "UserFoodFeedback", back_populates="food", cascade="all, delete-orphan"
    )


class FoodNutrient(Base):
    """قيمة مغذٍ لطعام أو وصفة لكل أساس وزن محدد."""

    __tablename__ = "food_nutrients"
    __table_args__ = (
        UniqueConstraint("food_id", "nutrient_code", name="uq_food_nutrient"),
        CheckConstraint("amount >= 0", name="ck_food_nutrient_amount_nonnegative"),
        CheckConstraint(
            "basis_grams > 0", name="ck_food_nutrient_basis_grams_positive"
        ),
        CheckConstraint(
            "data_quality IN ('verified', 'estimated')",
            name="ck_food_nutrient_data_quality_allowed",
        ),
    )

    id = Column(Integer, primary_key=True)
    food_id = Column(
        Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nutrient_code = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    unit = Column(String(30), nullable=False)
    basis_grams = Column(Float, nullable=False, default=100.0)
    data_quality = Column(String(20), nullable=False, default="verified")

    food = relationship("Food", back_populates="nutrients")


class FoodPortion(Base):
    """حصة قابلة للعرض والتحويل إلى غرامات."""

    __tablename__ = "food_portions"
    __table_args__ = (
        UniqueConstraint("food_id", "label", name="uq_food_portion_label"),
        CheckConstraint("grams > 0", name="ck_food_portion_grams_positive"),
    )

    id = Column(Integer, primary_key=True)
    food_id = Column(
        Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label = Column(String(100), nullable=False)
    grams = Column(Float, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)

    food = relationship("Food", back_populates="portions")


# ── المكونات ومسببات الحساسية ─────────────────────────────


class Ingredient(Base):
    """مكوّن معياري يمكن ربطه بطعام أو وصفة وبمسبب حساسية."""

    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    canonical_name = Column(String(255), nullable=False, unique=True, index=True)
    display_name_ar = Column(String(255), nullable=False)
    description = Column(Text)

    food_links = relationship("FoodIngredient", back_populates="ingredient")
    allergen_records = relationship("IngredientAllergen", back_populates="ingredient")


class FoodIngredient(Base):
    """يربط صنفًا غذائيًا أو وصفة بمكوّناتها المعلنة."""

    __tablename__ = "food_ingredients"
    __table_args__ = (
        UniqueConstraint("food_id", "ingredient_id", name="uq_food_ingredient"),
        CheckConstraint(
            "amount_g IS NULL OR amount_g >= 0",
            name="ck_food_ingredient_amount_nonnegative",
        ),
    )

    id = Column(Integer, primary_key=True)
    food_id = Column(
        Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id"), nullable=False, index=True
    )
    amount_g = Column(Float)
    role = Column(String(50), nullable=False, default="primary")
    is_optional = Column(Boolean, nullable=False, default=False)

    food = relationship("Food", back_populates="ingredient_links")
    ingredient = relationship("Ingredient", back_populates="food_links")


class Allergen(Base):
    """قاموس مسببات الحساسية/المواد التي تحتاج تتبعًا صريحًا."""

    __tablename__ = "allergens"

    id = Column(Integer, primary_key=True)
    code = Column(String(100), nullable=False, unique=True, index=True)
    display_name_ar = Column(String(255), nullable=False)
    display_name_en = Column(String(255))
    description = Column(Text)

    ingredient_records = relationship("IngredientAllergen", back_populates="allergen")
    food_records = relationship("FoodAllergen", back_populates="allergen")


class IngredientAllergen(Base):
    """دليل مسبب الحساسية على مستوى المكوّن."""

    __tablename__ = "ingredient_allergens"
    __table_args__ = (
        UniqueConstraint(
            "ingredient_id", "allergen_id", name="uq_ingredient_allergen"
        ),
        CheckConstraint(
            "status IN ('present', 'absent', 'unknown')",
            name="ck_ingredient_allergen_status_allowed",
        ),
    )

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    allergen_id = Column(
        Integer, ForeignKey("allergens.id"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="unknown")
    source_id = Column(Integer, ForeignKey("catalog_sources.id"))
    reviewed_at = Column(DateTime)

    ingredient = relationship("Ingredient", back_populates="allergen_records")
    allergen = relationship("Allergen", back_populates="ingredient_records")
    source = relationship("CatalogSource", back_populates="ingredient_allergen_records")


class FoodAllergen(Base):
    """حالة مسبب الحساسية النهائية لطعام أو وصفة قابلة للتدقيق."""

    __tablename__ = "food_allergens"
    __table_args__ = (
        UniqueConstraint("food_id", "allergen_id", name="uq_food_allergen"),
        CheckConstraint(
            "status IN ('present', 'absent', 'unknown')",
            name="ck_food_allergen_status_allowed",
        ),
    )

    id = Column(Integer, primary_key=True)
    food_id = Column(
        Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allergen_id = Column(
        Integer, ForeignKey("allergens.id"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="unknown")
    source_id = Column(Integer, ForeignKey("catalog_sources.id"))
    is_derived = Column(Boolean, nullable=False, default=False)
    reviewed_at = Column(DateTime)

    food = relationship("Food", back_populates="allergen_records")
    allergen = relationship("Allergen", back_populates="food_records")
    source = relationship("CatalogSource", back_populates="food_allergen_records")
