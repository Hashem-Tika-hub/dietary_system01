# ============================================================
#  api/schemas.py — نماذج البيانات (Request / Response)
#  Pydantic يتحقق تلقائياً من صحة البيانات الواردة
# ============================================================

from datetime import date, datetime
from math import isfinite
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# نطاقات تحقق تقنية تمنع الإدخالات الشاذة الواضحة. لا تستخدم للتشخيص الطبي.
MIN_PROFILE_AGE = 10
MAX_PROFILE_AGE = 100
MIN_REASONABLE_BMI = 10.0
MAX_REASONABLE_BMI = 80.0


def validate_body_profile_sanity(*, age: int, weight: float, height: float) -> None:
    """Reject technically implausible body-profile values before persistence.

    BMI is used here only as a data-quality sanity check after individual field
    limits have passed; it is not a medical diagnosis or recommendation.
    """
    if not MIN_PROFILE_AGE <= age <= MAX_PROFILE_AGE:
        raise ValueError(
            f"العمر يجب أن يكون بين {MIN_PROFILE_AGE} و{MAX_PROFILE_AGE} سنة"
        )
    if not isfinite(weight) or not isfinite(height):
        raise ValueError("الوزن والطول يجب أن يكونا قيمتين رقميتين منتهيتين")

    bmi = weight / ((height / 100) ** 2)
    if not MIN_REASONABLE_BMI <= bmi <= MAX_REASONABLE_BMI:
        raise ValueError("تركيبة الوزن والطول غير منطقية؛ راجع البيانات المدخلة")


# ══════════════════════════════════════════════════════════
#  المستخدم
# ══════════════════════════════════════════════════════════

class UserRegister(BaseModel):
    """بيانات تسجيل مستخدم جديد"""
    email:    EmailStr
    password: str = Field(min_length=6)
    name:     str = Field(default="مستخدم", min_length=1, max_length=100)

    # بيانات الجسم
    age:            int   = Field(ge=MIN_PROFILE_AGE, le=MAX_PROFILE_AGE)
    gender:         str   = Field(default="male", pattern="^(male|female)$")
    weight:         float = Field(ge=30, le=300, allow_inf_nan=False)
    height:         float = Field(ge=100, le=250, allow_inf_nan=False)
    activity_level: int   = Field(default=2, ge=1, le=5)

    # الهدف والصحة
    goal:           str  = Field(default="maintain",
                                  pattern="^(lose|maintain|gain|sport)$")
    has_diabetes:    bool = False
    has_bp:          bool = False
    has_cholesterol: bool = False
    allergies:       List[str] = []

    # تفضيلات الطعام التفصيلية
    # القيم المتاحة: بحريات, دواجن, لحوم_حمراء, بيض, ألبان, مكسرات, بقوليات, حلويات
    dislikes:       List[str] = Field(default=[], description="أطعمة لا يفضّلها (تُستبعد كليًا)")
    favorites:      List[str] = Field(default=[], description="أطعمة مفضّلة (تُرجَّح بالترتيب)")
    cuisine_style:  str = Field(default="مزيج", pattern="^(تقليدي|عالمي|مزيج)$",
                                 description="تقليدي = أطباق محلية/عربية، عالمي = أطباق عامة أبسط")
    allow_treats:   bool = Field(default=False, description="السماح بظهور حلويات كخيار مناسبات")

    @model_validator(mode="after")
    def validate_profile_sanity(self) -> "UserRegister":
        validate_body_profile_sanity(
            age=self.age,
            weight=self.weight,
            height=self.height,
        )
        return self

    model_config = {
        "str_strip_whitespace": True,
        "json_schema_extra": {"example": {
        "email": "omar@example.com", "password": "secret123",
        "name": "عمر", "age": 24, "gender": "male",
        "weight": 78.0, "height": 178.0, "activity_level": 3,
        "goal": "gain", "has_diabetes": False,
        "has_bp": False, "has_cholesterol": False, "allergies": [],
        "dislikes": ["بحريات"], "favorites": ["دواجن"],
        "cuisine_style": "تقليدي", "allow_treats": False
    }},
    }


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserUpdate(BaseModel):
    """تحديث جزئي للملف الشخصي"""
    name:           Optional[str]   = Field(default=None, min_length=1, max_length=100)
    age:            Optional[int]   = Field(default=None, ge=MIN_PROFILE_AGE, le=MAX_PROFILE_AGE)
    gender:         Optional[str]   = Field(default=None, pattern="^(male|female)$")
    weight:         Optional[float] = Field(default=None, ge=30, le=300, allow_inf_nan=False)
    height:         Optional[float] = Field(default=None, ge=100, le=250, allow_inf_nan=False)
    activity_level: Optional[int]   = Field(default=None, ge=1, le=5)
    goal:           Optional[str]   = Field(default=None, pattern="^(lose|maintain|gain|sport)$")
    has_diabetes:   Optional[bool]  = None
    has_bp:         Optional[bool]  = None
    has_cholesterol:Optional[bool]  = None
    allergies:      Optional[List[str]] = None
    dislikes:       Optional[List[str]] = None
    favorites:      Optional[List[str]] = None
    cuisine_style:  Optional[str]   = Field(default=None, pattern="^(تقليدي|عالمي|مزيج)$")
    allow_treats:   Optional[bool]  = None

    model_config = {"str_strip_whitespace": True}


class UserResponse(BaseModel):
    """بيانات المستخدم المُرجَعة للتطبيق"""
    id:             int
    email:          str
    name:           str
    age:            int
    gender:         str
    weight:         float
    height:         float
    activity_level: int
    goal:           str
    has_diabetes:   bool
    has_bp:         bool
    has_cholesterol:bool
    allergies:      List[str]
    dislikes:       List[str] = []
    favorites:      List[str] = []
    cuisine_style:  str = "مزيج"
    allow_treats:   bool = False
    created_at:     datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════
#  المصادقة
# ══════════════════════════════════════════════════════════

class Token(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


# ══════════════════════════════════════════════════════════
#  الاحتياجات الغذائية
# ══════════════════════════════════════════════════════════

class MealTarget(BaseModel):
    label:    str
    calories: float
    protein:  float
    carbs:    float
    fat:      float


class NutritionTargets(BaseModel):
    daily_calories: float
    protein_g:      float
    carbs_g:        float
    fat_g:          float
    bmi:            float
    bmr:            float
    tdee:           float
    meal_targets:   Dict[str, MealTarget]


# ══════════════════════════════════════════════════════════
#  التوصيات
# ══════════════════════════════════════════════════════════

class MealRequest(BaseModel):
    """طلب توصيات وجبة واحدة"""
    meal:  str   = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    top_k: int   = Field(default=5, ge=1, le=20)


class FoodRecommendation(BaseModel):
    """طعام موصى به"""
    fdc_id:         str
    name:           str
    category:       str = ""
    food_group:     str = ""
    slot:           str = ""   # الخانة بالطبق: بروتين / نشويات / خضار ...
    calories:       float
    protein:        float
    carbs:          float
    fat:            float
    portion_g:      float = 100
    hybrid_score:   float = 0.0
    food_cluster:   Optional[int] = None
    recommendation_reason: str = ""
    recommendation_reasons: List[str] = []
    diversity_applied: bool = False


class MealRecommendationResponse(BaseModel):
    meal:          str
    meal_label:    str
    # الهدف المستخدم فعليًا لتحديد الحصص وترتيب التوصية بعد ميزانية اليوم.
    target_calories: float
    # الهدف المخطط للوجبة قبل خصم ما سُجل خلال اليوم.
    planned_target_calories: float = 0.0
    consumed_today_calories: float = 0.0
    remaining_daily_calories: float = 0.0
    budget_adjusted: bool = False
    daily_budget_exhausted: bool = False
    recommendations: List[FoodRecommendation]
    ranking_basis: str = "content_based"
    content_weight: float = 1.0
    collaborative_weight: float = 0.0


class WeeklyMealTotals(BaseModel):
    target_calories: float = 0.0
    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    calorie_delta: float = 0.0
    missing_required_slots: int = 0


class WeeklyDayTotals(BaseModel):
    planned_calories: float = 0.0
    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    calorie_delta: float = 0.0
    completion_ratio: float = 0.0
    missing_required_slots: int = 0
    meals: Dict[str, WeeklyMealTotals] = Field(default_factory=dict)


class WeeklyPlanChangeSummary(BaseModel):
    day: str
    meal: str
    slot: str
    meal_calories_delta: float = 0.0
    day_calories_delta: float = 0.0
    protein_delta_g: float = 0.0
    carbs_delta_g: float = 0.0
    fat_delta_g: float = 0.0


class WeeklyPlanResponse(BaseModel):
    """الخطة الأسبوعية ومجاميعها التخطيطية المشتقة من عناصرها."""
    id:      int
    plan:    Dict[str, Any]
    user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    totals: Dict[str, WeeklyDayTotals] = Field(default_factory=dict)
    change_summary: Optional[WeeklyPlanChangeSummary] = None


class SwapAlternativesRequest(BaseModel):
    """طلب بدائل لصنف معيّن داخل خطة محفوظة"""
    plan_id: int
    day:     str
    meal:    str
    slot:    str


class SwapRequest(BaseModel):
    """طلب تنفيذ استبدال صنف داخل خطة محفوظة"""
    plan_id:    int
    day:        str
    meal:       str
    slot:       str
    new_fdc_id: str


# ══════════════════════════════════════════════════════════
#  سجل الوجبات
# ══════════════════════════════════════════════════════════

class MealLogCreate(BaseModel):
    meal_type:  str   = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    food_name:  str   = Field(min_length=1, max_length=255)
    fdc_id:     str   = Field(default="", max_length=50)
    portion_g:  float = Field(default=100, ge=1)
    calories:   float = Field(default=0, ge=0)
    protein:    float = Field(default=0, ge=0)
    carbs:      float = Field(default=0, ge=0)
    fat:        float = Field(default=0, ge=0)
    notes:      str   = Field(default="", max_length=1000)


class MealLogUpdate(BaseModel):
    """تحديث جزئي لسجل وجبة يخص المستخدم الحالي فقط."""
    meal_type: Optional[str] = Field(
        default=None, pattern="^(breakfast|lunch|dinner|snack)$"
    )
    food_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    fdc_id: Optional[str] = Field(default=None, max_length=50)
    portion_g: Optional[float] = Field(default=None, ge=1)
    calories: Optional[float] = Field(default=None, ge=0)
    protein: Optional[float] = Field(default=None, ge=0)
    carbs: Optional[float] = Field(default=None, ge=0)
    fat: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class MealLogResponse(MealLogCreate):
    id:       int
    user_id:  int
    date:     datetime

    model_config = {"from_attributes": True}


class MealLogSummary(BaseModel):
    """ملخص استهلاك وجبات المستخدم ضمن نافذة زمنية اختيارية."""
    count: int
    calories: float
    protein: float
    carbs: float
    fat: float


class NutrientProgress(BaseModel):
    """هدف ومستهلك ومتَبقٍ لمغذٍ واحد في اليوم المحدد.

    هذه قيم متابعة حسابية للسجل الذي أدخله المستخدم، وليست تشخيصًا طبيًا.
    قد تكون ``remaining`` سالبة عند تجاوز المستخدم للهدف التقريبي.
    """
    target: float
    consumed: float
    remaining: float
    progress_ratio: float = Field(ge=0)


class DailyNutritionProgress(BaseModel):
    """ملخص اليوم المعروض في Dashboard.

    يستند الاستهلاك إلى MealLog في اليوم المطلوب فقط، بينما تحسب الأهداف من
    الملف الشخصي الحالي على الخادم لضمان اتساق الأرقام بين العميل والخادم.
    """
    date: date
    logged_meals: int
    calories: NutrientProgress
    protein: NutrientProgress
    carbs: NutrientProgress
    fat: NutrientProgress


# ══════════════════════════════════════════════════════════
#  التفاعلات الصريحة للتوصية التعاونية
# ══════════════════════════════════════════════════════════

class FoodFeedbackUpsert(BaseModel):
    """إشارة صريحة يختارها المستخدم عن طعام من الكتالوج الموثق.

    يقبل العقد ``food_id`` لعملاء API السابقين أو ``fdc_id`` الذي يصل من
    توصيات Flutter وCSV الكتالوج. يجب إرسال معرف واحد فقط لتجنب الغموض.
    """
    food_id: Optional[int] = Field(default=None, gt=0)
    fdc_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    event_type: str = Field(pattern="^(like|dislike|save|not_interested)$")

    @model_validator(mode="after")
    def require_exactly_one_food_identifier(self) -> "FoodFeedbackUpsert":
        if (self.food_id is None) == (self.fdc_id is None):
            raise ValueError("أرسل food_id أو fdc_id واحدًا فقط")
        return self


class FoodFeedbackResponse(BaseModel):
    id: int
    user_id: int
    food_id: int
    event_type: str
    score: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollaborativeReadinessResponse(BaseModel):
    ready: bool
    reason: str
    interaction_count: int
    unique_users: int
    unique_foods: int
    target_user_interactions: int


# ══════════════════════════════════════════════════════════
#  الأطعمة
# ══════════════════════════════════════════════════════════

class FoodItem(BaseModel):
    fdc_id:           str
    name:             str
    category:         str  = ""
    food_group:       str  = ""
    meal_type:        str  = ""
    source:           str  = ""
    calories:         float
    protein:          float
    carbs:            float
    fat:              float
    fiber:            float = 0
    health_score:     float = 0
    diabetic_friendly: bool = False
    low_sodium:        bool = False


class FoodSearchResponse(BaseModel):
    total:  int
    foods:  List[FoodItem]


class CatalogReadinessResponse(BaseModel):
    """توفر كتالوج الطعام واكتمال أدلة الحساسية، لا حكم طبي على الطعام."""
    active_foods: int
    foods_with_required_nutrients: int
    foods_missing_required_nutrients: int
    reference_allergens: int
    foods_with_any_allergen_evidence: int
    foods_missing_allergen_evidence: int
    foods_with_unknown_allergen_evidence: int
    foods_with_complete_reference_allergen_evidence: int
    catalog_loaded: bool
    allergy_evidence_complete: bool
    status: str
