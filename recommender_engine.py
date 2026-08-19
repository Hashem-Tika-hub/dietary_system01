# ============================================================
#  recommender_engine.py — واجهة نظيفة للنماذج
#  يُحمَّل مرة واحدة عند بدء السيرفر ويبقى في الذاكرة
# ============================================================

import importlib.util
import pickle
from pathlib import Path
from functools import lru_cache

from api.services.recommendation_policy import (
    effective_hybrid_weights,
    ranking_basis,
)

BASE  = Path(__file__).parent
MODEL = BASE / "models"


def _import(filename, alias):
    spec = importlib.util.spec_from_file_location(
        alias, BASE / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── تحميل الوحدات ─────────────────────────────────────────
_up  = _import("05_user_profiler.py",     "up")
_cbf = _import("07_cbf_model.py",         "cbf")
_cf  = _import("08_cf_model.py",          "cf")
_hr  = _import("09_hybrid_recommender.py","hr")
_mr  = _import("meal_rules.py",           "mr")

UserProfile       = _up.UserProfile
ContentBasedFilter= _cbf.ContentBasedFilter
CollaborativeFilter= _cf.CollaborativeFilter
HybridRecommender = _hr.HybridRecommender


# ── Singleton: يُحمَّل مرة واحدة فقط ─────────────────────
@lru_cache(maxsize=1)
def get_engine() -> HybridRecommender:
    hr = HybridRecommender(cbf_weight=0.60, cf_weight=0.40)
    hr.load_models()
    return hr


def build_user(data: dict) -> UserProfile:
    """بناء كائن UserProfile من dict قادم من API."""
    user = UserProfile(
        name            = data.get("name", "users"),
        age             = data["age"],
        gender          = data.get("gender", "male"),
        weight          = data["weight"],
        height          = data["height"],
        activity_level  = data.get("activity_level", 2),
        goal            = data.get("goal", "maintain"),
        has_diabetes    = data.get("has_diabetes", False),
        has_bp          = data.get("has_bp", False),
        has_cholesterol = data.get("has_cholesterol", False),
        allergies       = data.get("allergies", []),
        dislikes        = data.get("dislikes", []),
        favorites       = data.get("favorites", []),
        cuisine_style   = data.get("cuisine_style", "مزيج"),
        allow_treats    = data.get("allow_treats", False),
    )
    # These fields are operational evidence for ranking only. They are not
    # medical data and do not override hard food-safety filters.
    user.interaction_count = max(0, int(data.get("interaction_count", 0)))
    user.collaborative_signals_ready = bool(
        data.get("collaborative_signals_ready", False)
    )
    return user


def get_ranking_metadata(user_data: dict) -> dict:
    """Explain whether the active ranker is content-based or truly hybrid."""
    user = build_user(user_data)
    engine = get_engine()
    weights = effective_hybrid_weights(
        configured_content_weight=engine.cbf_weight,
        configured_collaborative_weight=engine.cf_weight,
        interaction_count=user.interaction_count,
        collaborative_signals_ready=user.collaborative_signals_ready,
    )
    return {
        "ranking_basis": ranking_basis(weights),
        "content_weight": weights.content,
        "collaborative_weight": weights.collaborative,
    }


def recommend_meal(user_data: dict, meal: str, top_k: int = 5) -> list:
    """
    توصيات وجبة واحدة — يرجع "طبق" (list من dicts)، صنف واحد لكل خانة
    (بروتين/نشويات/خضار...) بدل قائمة top_k مسطّحة. top_k محفوظ في
    التوقيع فقط للتوافق مع نداءات API القديمة ولا يُستخدَم الآن — حجم
    الطبق يحدده قالب الوجبة (meal_rules.PLATE_TEMPLATES) لا top_k.
    """
    user = build_user(user_data)
    engine = get_engine()
    return engine.recommend_meal(user, meal=meal)


def generate_weekly_plan(user_data: dict) -> dict:
    """خطة أسبوعية كاملة"""
    user = build_user(user_data)
    engine = get_engine()
    plan = engine.generate_weekly_plan(user, days=7)
    return plan


def get_swap_alternatives(user_data: dict, meal: str, slot: str,
                          current_fdc_id: str = None, top_k: int = 6) -> list:
    """
    بدائل ممكنة لصنف معيّن داخل خانة معيّنة (بروتين/نشويات/خضار...)
    بوجبة معيّنة — تُستخدم لميزة "استبدال الوجبة".
    """
    user = build_user(user_data)
    engine = get_engine()

    slot_info = _mr.get_slot_info(meal, slot)
    if not slot_info:
        return []

    exclude = [current_fdc_id] if current_fdc_id else None
    candidates = engine._score_candidates(user, meal, exclude_ids=exclude)
    if candidates.empty:
        return []

    eligible = candidates[candidates["food_group"].isin(slot_info["food_group"])]
    top = eligible.sort_values("hybrid_score", ascending=False).head(top_k)

    meal_targets = user.get_meal_targets()
    slot_target_cal = meal_targets[meal]["calories"] * slot_info["share"]

    results = []
    for _, row in top.iterrows():
        portion_g, portion_cal = _mr.compute_portion(
            float(row["calories"]), slot_target_cal, row["food_group"]
        )
        results.append({
            "fdc_id":       row["fdc_id"],
            "name":         row["name"],
            "category":     row["category"],
            "food_group":   row["food_group"],
            "slot":         slot,
            "portion_g":    float(portion_g),
            "calories":     float(portion_cal),
            "protein":      round(float(row["protein"]) * portion_g / 100, 1),
            "carbs":        round(float(row["carbs"])   * portion_g / 100, 1),
            "fat":          round(float(row["fat"])     * portion_g / 100, 1),
            "hybrid_score": round(float(row["hybrid_score"]), 3),
        })
    return results


def swap_meal_item(plan_data: dict, day: str, meal: str, slot: str,
                   new_fdc_id: str, user_data: dict) -> dict:
    """يستبدل صنفًا محددًا (بالخانة) داخل خطة محفوظة بصنف جديد، مع إعادة
    حساب حصته الواقعية حسب نفس حصة الخانة من هدف الوجبة."""
    user = build_user(user_data)
    engine = get_engine()

    foods_df = engine.cbf.foods_df
    match = foods_df[foods_df["fdc_id"] == new_fdc_id]
    if match.empty:
        raise ValueError(f"food not found: {new_fdc_id}")
    food = match.iloc[0]

    slot_info = _mr.get_slot_info(meal, slot)
    if not slot_info:
        raise ValueError(f"unknown slot: {meal}/{slot}")

    meal_targets = user.get_meal_targets()
    slot_target_cal = meal_targets[meal]["calories"] * slot_info["share"]
    portion_g, portion_cal = _mr.compute_portion(
        float(food["calories"]), slot_target_cal, food["food_group"]
    )

    new_item = {
        "fdc_id":       new_fdc_id,
        "name":         food["name"],
        "category":     food["category"],
        "food_group":   food["food_group"],
        "slot":         slot,
        "portion_g":    float(portion_g),
        "calories":     float(portion_cal),
        "protein":      round(float(food["protein"]) * portion_g / 100, 1),
        "carbs":        round(float(food["carbs"])   * portion_g / 100, 1),
        "fat":          round(float(food["fat"])     * portion_g / 100, 1),
        "hybrid_score": 1.0,   # اختيار المستخدم يدويًا
    }

    day_plan  = dict(plan_data.get(day, {}))
    meal_list = list(day_plan.get(meal, []))
    replaced  = False
    for i, item in enumerate(meal_list):
        if item.get("slot") == slot:
            meal_list[i] = new_item
            replaced = True
            break
    if not replaced:
        meal_list.append(new_item)

    day_plan[meal] = meal_list
    plan_data = dict(plan_data)
    plan_data[day] = day_plan
    return plan_data


def get_user_targets(user_data: dict) -> dict:
    """الاحتياجات الغذائية اليومية"""
    user = build_user(user_data)
    return {
        "daily_calories": user.daily_calories,
        "protein_g":      user.protein_g,
        "carbs_g":        user.carbs_g,
        "fat_g":          user.fat_g,
        "bmi":            user.bmi,
        "bmr":            user.bmr,
        "tdee":           user.tdee,
        "meal_targets":   user.get_meal_targets(),
    }