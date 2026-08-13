# ============================================================
#  api/schemas.py — نماذج البيانات (Request / Response)
#  Pydantic يتحقق تلقائياً من صحة البيانات الواردة
# ============================================================

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


# ══════════════════════════════════════════════════════════
#  المستخدم
# ══════════════════════════════════════════════════════════

class UserRegister(BaseModel):
    """بيانات تسجيل مستخدم جديد"""
    email:    EmailStr
    password: str = Field(min_length=6)
    name:     str = Field(default="مستخدم", max_length=100)

    # بيانات الجسم
    age:            int   = Field(ge=10, le=100)
    gender:         str   = Field(default="male", pattern="^(male|female)$")
    weight:         float = Field(ge=30, le=300)
    height:         float = Field(ge=100, le=250)
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

    model_config = {"json_schema_extra": {"example": {
        "email": "omar@example.com", "password": "secret123",
        "name": "عمر", "age": 24, "gender": "male",
        "weight": 78.0, "height": 178.0, "activity_level": 3,
        "goal": "gain", "has_diabetes": False,
        "has_bp": False, "has_cholesterol": False, "allergies": [],
        "dislikes": ["بحريات"], "favorites": ["دواجن"],
        "cuisine_style": "تقليدي", "allow_treats": False
    }}}


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserUpdate(BaseModel):
    """تحديث جزئي للملف الشخصي"""
    name:           Optional[str]   = None
    age:            Optional[int]   = Field(default=None, ge=10, le=100)
    gender:         Optional[str]   = Field(default=None, pattern="^(male|female)$")
    weight:         Optional[float] = Field(default=None, ge=30, le=300)
    height:         Optional[float] = Field(default=None, ge=100, le=250)
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


class MealRecommendationResponse(BaseModel):
    meal:          str
    meal_label:    str
    target_calories: float
    recommendations: List[FoodRecommendation]


class WeeklyPlanResponse(BaseModel):
    """الخطة الأسبوعية"""
    id:      int
    plan:    Dict[str, Any]
    user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    food_name:  str
    fdc_id:     str   = ""
    portion_g:  float = Field(default=100, ge=1)
    calories:   float = 0
    protein:    float = 0
    carbs:      float = 0
    fat:        float = 0
    notes:      str   = ""


class MealLogResponse(MealLogCreate):
    id:       int
    user_id:  int
    date:     datetime

    model_config = {"from_attributes": True}


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