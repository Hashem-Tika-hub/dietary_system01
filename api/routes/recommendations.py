# ============================================================
#  api/routes/recommendations.py
#  POST /recommendations/meal     — single meal suggestions
#  POST /recommendations/weekly   — full 7-day plan
#  GET  /recommendations/history  — past weekly plans
# ============================================================

import logging
from datetime import datetime, time, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from api.database     import get_db
from api.db_models    import MealLog, User, Food, UserFoodFeedback, WeeklyPlan
from api.services.feedback_collaborative_filter import (
    ExplicitFeedbackCollaborativeFilter,
    FeedbackRecord,
)
from api.services.allergen_eligibility import eligible_external_ids
from api.services.weekly_plan_totals import build_change_summary, summarize_week
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


def _user_dict(user: User, db: Session | None = None) -> dict:
    interaction_count = 0
    collaborative_signals_ready = False
    explicit_collaborative_scores: dict[str, float] = {}

    if db is not None:
        feedback_rows = db.query(UserFoodFeedback).all()
        feedback_filter = ExplicitFeedbackCollaborativeFilter().fit(
            FeedbackRecord(
                user_id=row.user_id, food_id=row.food_id, score=row.score
            )
            for row in feedback_rows
        )
        readiness = feedback_filter.readiness_for(user.id)
        interaction_count = readiness.target_user_interactions
        collaborative_signals_ready = readiness.ready

        if readiness.ready:
            scores_by_food_id = feedback_filter.score_unseen_foods(user.id)
            if scores_by_food_id:
                catalog_foods = db.query(Food).filter(
                    Food.id.in_(scores_by_food_id), Food.is_active.is_(True)
                ).all()
                explicit_collaborative_scores = {
                    str(food.external_id): scores_by_food_id[food.id]
                    for food in catalog_foods
                }

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
        "interaction_count": interaction_count,
        "collaborative_signals_ready": collaborative_signals_ready,
        "explicit_collaborative_scores": explicit_collaborative_scores,
    }


def _catalog_eligible_fdc_ids(user: User, db: Session) -> set[str] | None:
    """Return catalog-backed safe candidates for declared allergies.

    Returning ``None`` when no allergy is declared preserves the standard CBF
    candidate pool.  A declared allergy returns a concrete set, possibly empty,
    so unknown catalog evidence cannot be ranked as if it were safe.
    """
    if not (user.allergies or []):
        return None
    return eligible_external_ids(
        db,
        engine.catalog_candidate_fdc_ids(),
        user.allergies or [],
    )


def _weekly_plan_response(
    plan_row: WeeklyPlan,
    user: User,
    db: Session,
    *,
    change_summary: dict | None = None,
) -> WeeklyPlanResponse:
    targets = engine.get_user_targets(_user_dict(user, db))
    totals = summarize_week(plan_row.plan_data, targets)
    return WeeklyPlanResponse(
        id=plan_row.id,
        plan=plan_row.plan_data,
        user_id=user.id,
        created_at=plan_row.created_at,
        totals=totals,
        change_summary=change_summary,
    )


def _today_calories_consumed(db: Session, user_id: int) -> float:
    """Return logged calories for the current calendar day, not preference data."""
    day_start = datetime.combine(datetime.now().date(), time.min)
    next_day_start = day_start + timedelta(days=1)
    return float(
        db.query(func.coalesce(func.sum(MealLog.calories), 0.0))
        .filter(
            MealLog.user_id == user_id,
            MealLog.date >= day_start,
            MealLog.date < next_day_start,
        )
        .scalar()
        or 0.0
    )


@router.post("/meal", response_model=MealRecommendationResponse,
             summary="Get meal recommendations")
def recommend_meal(
    req:  MealRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user)
):
    """
    Returns top-K food recommendations for a specific meal.

    - Applies hard health and allergy filters before ranking
    - Uses content-based ranking by default; hybrid CF activates only after
      enough explicit, consented feedback records pass the readiness gate
    - Includes suggested portion size in grams and ranking metadata
    """
    try:
        user_data = _user_dict(user, db)
        targets = engine.get_user_targets(user_data)
        ranking = engine.get_ranking_metadata(user_data)

        planned_meal_calories = float(targets["meal_targets"][req.meal]["calories"])
        daily_target_calories = float(targets["daily_calories"])
        consumed_today_calories = _today_calories_consumed(db, user.id)
        remaining_daily_calories = max(
            0.0,
            daily_target_calories - consumed_today_calories,
        )
        effective_meal_calories = min(
            planned_meal_calories,
            remaining_daily_calories,
        )
        daily_budget_exhausted = remaining_daily_calories <= 0.0

        # MealLog changes the nutritional budget only. It never adds a
        # preference signal and does not change CF readiness or its weights.
        catalog_eligible_ids = _catalog_eligible_fdc_ids(user, db)
        recommendation_kwargs = {"meal_target_calories": effective_meal_calories}
        if catalog_eligible_ids is not None:
            recommendation_kwargs["eligible_fdc_ids"] = catalog_eligible_ids
        items = (
            []
            if daily_budget_exhausted
            else engine.recommend_meal(
                user_data,
                req.meal,
                req.top_k,
                **recommendation_kwargs,
            )
        )

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
            food_cluster = r.get("food_cluster"),
            recommendation_reason = str(r.get("recommendation_reason", "")),
            recommendation_reasons = list(r.get("recommendation_reasons", [])),
            diversity_applied = bool(r.get("diversity_applied", False)),
        ) for r in items]

        return MealRecommendationResponse(
            meal            = req.meal,
            meal_label      = MEAL_LABELS.get(req.meal, req.meal),
            target_calories = effective_meal_calories,
            planned_target_calories = planned_meal_calories,
            consumed_today_calories = consumed_today_calories,
            remaining_daily_calories = remaining_daily_calories,
            budget_adjusted = effective_meal_calories < planned_meal_calories,
            daily_budget_exhausted = daily_budget_exhausted,
            recommendations = recs,
            **ranking,
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
        return _weekly_plan_response(existing, user, db)

    try:
        catalog_eligible_ids = _catalog_eligible_fdc_ids(user, db)
        plan_kwargs = {}
        if catalog_eligible_ids is not None:
            plan_kwargs["eligible_fdc_ids"] = catalog_eligible_ids
        plan = engine.generate_weekly_plan(_user_dict(user, db), **plan_kwargs)
        record = WeeklyPlan(user_id=user.id, plan_data=plan)
        db.add(record); db.commit(); db.refresh(record)
        return _weekly_plan_response(record, user, db)
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
        catalog_eligible_ids = _catalog_eligible_fdc_ids(user, db)
        plan_kwargs = {}
        if catalog_eligible_ids is not None:
            plan_kwargs["eligible_fdc_ids"] = catalog_eligible_ids
        plan = engine.generate_weekly_plan(_user_dict(user, db), **plan_kwargs)
        record = WeeklyPlan(user_id=user.id, plan_data=plan)
        db.add(record); db.commit(); db.refresh(record)
        return _weekly_plan_response(record, user, db)
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
        catalog_eligible_ids = _catalog_eligible_fdc_ids(user, db)
        alternatives_kwargs = {}
        if catalog_eligible_ids is not None:
            alternatives_kwargs["eligible_fdc_ids"] = catalog_eligible_ids
        alts = engine.get_swap_alternatives(
            _user_dict(user, db),
            req.meal,
            req.slot,
            current_fdc,
            **alternatives_kwargs,
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
        user_data = _user_dict(user, db)
        targets = engine.get_user_targets(user_data)
        before_totals = summarize_week(plan_row.plan_data, targets)
        catalog_eligible_ids = _catalog_eligible_fdc_ids(user, db)
        swap_kwargs = {}
        if catalog_eligible_ids is not None:
            swap_kwargs["eligible_fdc_ids"] = catalog_eligible_ids
        updated = engine.swap_meal_item(
            dict(plan_row.plan_data),
            req.day,
            req.meal,
            req.slot,
            req.new_fdc_id,
            user_data,
            **swap_kwargs,
        )
        after_totals = summarize_week(updated, targets)
        change_summary = build_change_summary(
            day=req.day,
            meal=req.meal,
            slot=req.slot,
            before_totals=before_totals,
            after_totals=after_totals,
        )
        plan_row.plan_data = updated
        flag_modified(plan_row, "plan_data")  # عمود JSON — SQLAlchemy لا يتتبّع التعديل داخل نفس الكائن تلقائيًا
        db.commit(); db.refresh(plan_row)
        return _weekly_plan_response(
            plan_row,
            user,
            db,
            change_summary=change_summary,
        )
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