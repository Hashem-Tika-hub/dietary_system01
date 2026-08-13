# ============================================================
#  api/routes/recommendations.py
#  POST /recommendations/meal     — single meal suggestions
#  POST /recommendations/weekly   — full 7-day plan
#  GET  /recommendations/history  — past weekly plans
# ============================================================

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from api.database     import get_db
from api.db_models    import User, WeeklyPlan
from api.schemas      import (MealRequest, MealRecommendationResponse,
                               FoodRecommendation, WeeklyPlanResponse,
                               SwapAlternativesRequest, SwapRequest)
from api.dependencies import get_current_user

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import recommender_engine as engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

MEAL_LABELS = {
    "breakfast": "Breakfast",
    "lunch":     "Lunch",
    "dinner":    "Dinner",
    "snack":     "Snack",
}


def _user_dict(user: User) -> dict:
    return {
        "name":            user.name,
        "age":             user.age,
        "gender":          user.gender,
        "weight":          user.weight,
        "height":          user.height,
        "activity_level":  user.activity_level,
        "goal":            user.goal,
        "has_diabetes":    user.has_diabetes,
        "has_bp":          user.has_bp,
        "has_cholesterol": user.has_cholesterol,
        "allergies":       user.allergies or [],
        "dislikes":        user.dislikes or [],
        "favorites":       user.favorites or [],
        "cuisine_style":   user.cuisine_style or "مزيج",
        "allow_treats":    user.allow_treats or False,
    }


@router.post("/meal", response_model=MealRecommendationResponse,
             summary="Get meal recommendations")
def recommend_meal(
    req:  MealRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    """
    Returns top-K food recommendations for a specific meal.

    - Applies health filters (diabetes, blood pressure, allergies)
    - Uses CBF (60%) + CF (40%) hybrid scoring
    - Includes suggested portion size in grams
    """
    try:
        items = engine.recommend_meal(_user_dict(user), req.meal, req.top_k)
        targets = engine.get_user_targets(_user_dict(user))
        meal_cal = targets["meal_targets"][req.meal]["calories"]

        recs = [FoodRecommendation(
            fdc_id       = str(r.get("fdc_id", "")),
            name         = str(r.get("name", "")),
            category     = str(r.get("category", "")),
            food_group   = str(r.get("food_group", "")),
            slot         = str(r.get("slot", "")),
            calories     = float(r.get("calories", 0)),
            protein      = float(r.get("protein", 0)),
            carbs        = float(r.get("carbs", 0)),
            fat          = float(r.get("fat", 0)),
            portion_g    = float(r.get("portion_g", 100)),
            hybrid_score = float(r.get("hybrid_score", 0)),
        ) for r in items]

        return MealRecommendationResponse(
            meal            = req.meal,
            meal_label      = MEAL_LABELS.get(req.meal, req.meal),
            target_calories = meal_cal,
            recommendations = recs,
        )

    except Exception as e:
        logger.exception("Recommendation error")
        raise HTTPException(status_code=500,
                            detail="حدث خطأ أثناء توليد التوصية، حاول لاحقًا")


@router.get("/weekly", response_model=WeeklyPlanResponse,
            summary="Get current weekly plan (generates once if none exists)")
def get_current_weekly(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    """
    يرجع آخر خطة أسبوعية محفوظة للمستخدم دون توليد جديد. لو لا توجد
    خطة محفوظة بعد (أول استخدام)، يولّد واحدة ويحفظها. هذا يمنع توليد
    خطة عشوائية جديدة في كل مرة يفتح فيها المستخدم شاشة الخطة.
    """
    existing = (db.query(WeeklyPlan)
                  .filter(WeeklyPlan.user_id == user.id)
                  .order_by(WeeklyPlan.created_at.desc())
                  .first())
    if existing:
        return WeeklyPlanResponse(id=existing.id, plan=existing.plan_data,
                                   user_id=user.id, created_at=existing.created_at)

    try:
        plan = engine.generate_weekly_plan(_user_dict(user))
        record = WeeklyPlan(user_id=user.id, plan_data=plan)
        db.add(record); db.commit(); db.refresh(record)
        return WeeklyPlanResponse(id=record.id, plan=plan, user_id=user.id,
                                   created_at=record.created_at)
    except Exception as e:
        logger.exception("Weekly plan generation error")
        raise HTTPException(status_code=500,
                            detail="حدث خطأ أثناء توليد الخطة الأسبوعية، حاول لاحقًا")


@router.post("/weekly", response_model=WeeklyPlanResponse,
             summary="Force-generate a brand new weekly plan")
def regenerate_weekly(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    """يولّد خطة أسبوعية جديدة كليًا ويحفظها كأحدث خطة — يُستخدم فقط عند
    ضغط المستخدم على زر "توليد خطة جديدة" الصريح."""
    try:
        plan = engine.generate_weekly_plan(_user_dict(user))
        record = WeeklyPlan(user_id=user.id, plan_data=plan)
        db.add(record); db.commit(); db.refresh(record)
        return WeeklyPlanResponse(id=record.id, plan=plan, user_id=user.id,
                                   created_at=record.created_at)
    except Exception as e:
        logger.exception("Weekly plan generation error")
        raise HTTPException(status_code=500,
                            detail="حدث خطأ أثناء توليد الخطة الأسبوعية، حاول لاحقًا")


@router.post("/weekly/alternatives", response_model=List[FoodRecommendation],
             summary="Get swap alternatives for one meal item in a saved plan")
def weekly_alternatives(
    req:  SwapAlternativesRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    plan_row = (db.query(WeeklyPlan)
                  .filter(WeeklyPlan.id == req.plan_id, WeeklyPlan.user_id == user.id)
                  .first())
    if not plan_row:
        raise HTTPException(status_code=404, detail="Plan not found")

    day_meal = plan_row.plan_data.get(req.day, {}).get(req.meal, [])
    current = next((it for it in day_meal if it.get("slot") == req.slot), None)
    current_fdc = current.get("fdc_id") if current else None

    try:
        alts = engine.get_swap_alternatives(
            _user_dict(user), req.meal, req.slot, current_fdc
        )
        return [FoodRecommendation(**a) for a in alts]
    except Exception as e:
        logger.exception("Alternatives error")
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء توليد البدائل، حاول لاحقًا")


@router.post("/weekly/swap", response_model=WeeklyPlanResponse,
             summary="Swap one meal item in a saved plan and persist it")
def weekly_swap(
    req:  SwapRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    plan_row = (db.query(WeeklyPlan)
                  .filter(WeeklyPlan.id == req.plan_id, WeeklyPlan.user_id == user.id)
                  .first())
    if not plan_row:
        raise HTTPException(status_code=404, detail="Plan not found")

    try:
        updated = engine.swap_meal_item(
            dict(plan_row.plan_data), req.day, req.meal, req.slot,
            req.new_fdc_id, _user_dict(user)
        )
        plan_row.plan_data = updated
        flag_modified(plan_row, "plan_data")  # عمود JSON — SQLAlchemy لا يتتبّع التعديل داخل نفس الكائن تلقائيًا
        db.commit(); db.refresh(plan_row)
        return WeeklyPlanResponse(id=plan_row.id, plan=plan_row.plan_data,
                                   user_id=user.id, created_at=plan_row.created_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Swap error")
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء التبديل، حاول لاحقًا")


@router.get("/history", summary="Get past weekly plans")
def get_history(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    """Returns the last 5 generated weekly plans for the user."""
    plans = (db.query(WeeklyPlan)
               .filter(WeeklyPlan.user_id == user.id)
               .order_by(WeeklyPlan.created_at.desc())
               .limit(5).all())

    return [{"id": p.id, "created_at": p.created_at, "plan": p.plan_data}
            for p in plans]