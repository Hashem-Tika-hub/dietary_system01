# ============================================================
#  api/routes/users.py — مسارات إدارة الملف الشخصي
#  GET  /users/profile           — عرض الملف الشخصي
#  PUT  /users/profile           — تعديل الملف الشخصي
#  GET  /users/nutrition-targets — الاحتياجات الغذائية
#  GET  /users/meal-logs         — سجل الوجبات
#  POST /users/meal-logs         — تسجيل وجبة جديدة
# ============================================================

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.database     import get_db
from api.db_models    import User, MealLog, Food, UserFoodFeedback
from api.schemas      import (UserResponse, UserUpdate,
                               NutritionTargets, MealTarget,
                               MealLogCreate, MealLogUpdate, MealLogResponse,
                               MealLogSummary, FoodFeedbackUpsert,
                               FoodFeedbackResponse, CollaborativeReadinessResponse,
                               validate_body_profile_sanity)
from api.services.feedback_collaborative_filter import (
    ExplicitFeedbackCollaborativeFilter,
    FeedbackRecord,
)
from api.dependencies import get_current_user
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import recommender_engine as engine

router = APIRouter(prefix="/users", tags=["المستخدم"])

FEEDBACK_SCORES = {
    "like": 1.0,
    "save": 0.5,
    "dislike": -1.0,
    "not_interested": -1.0,
}


def _feedback_filter(db: Session) -> ExplicitFeedbackCollaborativeFilter:
    records = db.query(UserFoodFeedback).all()
    return ExplicitFeedbackCollaborativeFilter().fit(
        FeedbackRecord(user_id=row.user_id, food_id=row.food_id, score=row.score)
        for row in records
    )


@router.get("/profile", response_model=UserResponse,
            summary="عرض الملف الشخصي")
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=UserResponse,
            summary="تعديل الملف الشخصي")
def update_profile(
    updates: UserUpdate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    """
    تحديث جزئي — يمكنك إرسال أي حقل تريد تغييره فقط
    """
    data = updates.model_dump(exclude_none=True)

    # UserUpdate is partial, so validate the prospective complete profile rather
    # than validating only fields present in this request.
    try:
        validate_body_profile_sanity(
            age=data.get("age", user.age),
            weight=data.get("weight", user.weight),
            height=data.get("height", user.height),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    for field, value in data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.get("/nutrition-targets", response_model=NutritionTargets,
            summary="الاحتياجات الغذائية اليومية")
def get_nutrition_targets(current_user: User = Depends(get_current_user)):
    """
    يحسب BMR, TDEE, وتوزيع المغذيات بناءً على بيانات المستخدم
    """
    user_data = {
        "name":            current_user.name,
        "age":             current_user.age,
        "gender":          current_user.gender,
        "weight":          current_user.weight,
        "height":          current_user.height,
        "activity_level":  current_user.activity_level,
        "goal":            current_user.goal,
        "has_diabetes":    current_user.has_diabetes,
        "has_bp":          current_user.has_bp,
        "has_cholesterol": current_user.has_cholesterol,
        "allergies":       current_user.allergies or [],
    }
    targets = engine.get_user_targets(user_data)

    # حوّل meal_targets إلى النموذج الصحيح
    meal_t = {
        k: MealTarget(**v)
        for k, v in targets["meal_targets"].items()
    }
    return NutritionTargets(**{**targets, "meal_targets": meal_t})


@router.get("/meal-logs", response_model=List[MealLogResponse],
            summary="سجل الوجبات")
def get_meal_logs(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    logs = (db.query(MealLog)
              .filter(MealLog.user_id == user.id)
              .order_by(MealLog.date.desc())
              .offset(offset).limit(limit).all())
    return logs


@router.get("/meal-logs/summary", response_model=MealLogSummary,
            summary="ملخص استهلاك الوجبات")
def get_meal_log_summary(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """يحسِب مجموع المغذيات في سجلات المستخدم ضمن نافذة زمنية اختيارية."""
    query = db.query(MealLog).filter(MealLog.user_id == user.id)
    if date_from:
        query = query.filter(MealLog.date >= date_from)
    if date_to:
        query = query.filter(MealLog.date <= date_to)

    count, calories, protein, carbs, fat = query.with_entities(
        func.count(MealLog.id),
        func.coalesce(func.sum(MealLog.calories), 0.0),
        func.coalesce(func.sum(MealLog.protein), 0.0),
        func.coalesce(func.sum(MealLog.carbs), 0.0),
        func.coalesce(func.sum(MealLog.fat), 0.0),
    ).one()
    return MealLogSummary(
        count=int(count), calories=float(calories), protein=float(protein),
        carbs=float(carbs), fat=float(fat),
    )


@router.post("/food-feedback", response_model=FoodFeedbackResponse,
             status_code=201, summary="حفظ تفاعل صريح مع طعام")
def upsert_food_feedback(
    data: FoodFeedbackUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """يحفظ آخر تفضيل صريح للمستخدم تجاه طعام من الكتالوج.

    لا يُستنتج التفاعل من سجل الوجبات. هذا الفصل يمنع أن يُفسَّر تناول
    المستخدم لطعام ما على أنه إعجاب أو تفضيل لتدريب النموذج التعاوني.
    """
    food = db.query(Food).filter(Food.id == data.food_id, Food.is_active.is_(True)).first()
    if not food:
        raise HTTPException(status_code=404, detail="الطعام غير موجود أو غير نشط")

    feedback = db.query(UserFoodFeedback).filter(
        UserFoodFeedback.user_id == user.id,
        UserFoodFeedback.food_id == data.food_id,
    ).first()
    if feedback:
        feedback.event_type = data.event_type
        feedback.score = FEEDBACK_SCORES[data.event_type]
    else:
        feedback = UserFoodFeedback(
            user_id=user.id,
            food_id=data.food_id,
            event_type=data.event_type,
            score=FEEDBACK_SCORES[data.event_type],
        )
        db.add(feedback)

    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/food-feedback/readiness", response_model=CollaborativeReadinessResponse,
            summary="حالة جاهزية التوصية التعاونية")
def get_collaborative_readiness(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """يوضح لماذا يعمل النموذج التعاوني أو لماذا يبقى في وضع cold start."""
    readiness = _feedback_filter(db).readiness_for(user.id)
    return CollaborativeReadinessResponse(
        ready=readiness.ready,
        reason=readiness.reason,
        interaction_count=readiness.interaction_count,
        unique_users=readiness.unique_users,
        unique_foods=readiness.unique_foods,
        target_user_interactions=readiness.target_user_interactions,
    )


@router.post("/meal-logs", response_model=MealLogResponse,
             status_code=201, summary="تسجيل وجبة جديدة")
def add_meal_log(
    data: MealLogCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    """تسجيل وجبة أكلها المستخدم لتتبع استهلاكه"""
    log = MealLog(user_id=user.id, **data.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.delete("/meal-logs/{log_id}", status_code=204,
               summary="حذف سجل وجبة")
def delete_meal_log(
    log_id: int,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    log = db.query(MealLog).filter(
        MealLog.id == log_id,
        MealLog.user_id == user.id
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    db.delete(log)
    db.commit()


@router.get("/meal-logs/{log_id}", response_model=MealLogResponse,
            summary="عرض سجل وجبة")
def get_meal_log(
    log_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """يرجع سجلًا واحدًا يملكه المستخدم الحالي، أو 404 دون كشف سجلات غيره."""
    log = db.query(MealLog).filter(
        MealLog.id == log_id,
        MealLog.user_id == user.id,
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return log


@router.patch("/meal-logs/{log_id}", response_model=MealLogResponse,
              summary="تحديث سجل وجبة")
def update_meal_log(
    log_id: int,
    updates: MealLogUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """يحدّث الحقول المرسلة فقط بعد التحقق من ملكية السجل."""
    log = db.query(MealLog).filter(
        MealLog.id == log_id,
        MealLog.user_id == user.id,
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="السجل غير موجود")

    for field, value in updates.model_dump(exclude_none=True).items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return log
