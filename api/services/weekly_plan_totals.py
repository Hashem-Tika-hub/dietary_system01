"""Deterministic summaries for planned weekly meals and swap deltas.

These helpers operate only on a WeeklyPlan's stored items. They deliberately do
not read MealLog records and do not create collaborative-feedback signals.
"""

from __future__ import annotations

from typing import Any, Mapping


_NUTRIENT_FIELDS = {
    "calories": "calories",
    "protein_g": "protein",
    "carbs_g": "carbs",
    "fat_g": "fat",
}


def _number(value: Any) -> float:
    """Convert a stored numeric value to a finite plan total contribution."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed >= 0 else 0.0


def _round(value: float) -> float:
    return round(float(value), 1)


def summarize_meal(items: list[Mapping[str, Any]], target_calories: float) -> dict[str, Any]:
    """Return visible planned totals for one meal without inventing missing data."""
    totals = {field: 0.0 for field in _NUTRIENT_FIELDS}
    missing_required_slots = 0

    for item in items or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("missing"):
            missing_required_slots += 1
            continue
        for output_field, item_field in _NUTRIENT_FIELDS.items():
            totals[output_field] += _number(item.get(item_field, 0.0))

    target = _number(target_calories)
    calories = _round(totals["calories"])
    return {
        "target_calories": _round(target),
        "calories": calories,
        "protein_g": _round(totals["protein_g"]),
        "carbs_g": _round(totals["carbs_g"]),
        "fat_g": _round(totals["fat_g"]),
        "calorie_delta": _round(calories - target),
        "missing_required_slots": missing_required_slots,
    }


def summarize_day(
    day_plan: Mapping[str, list[Mapping[str, Any]]],
    meal_targets: Mapping[str, Mapping[str, Any]],
    daily_target_calories: float,
) -> dict[str, Any]:
    """Summarize all planned meals for a day using profile-based plan targets."""
    meals: dict[str, dict[str, Any]] = {}
    for meal, target in meal_targets.items():
        meals[meal] = summarize_meal(
            list(day_plan.get(meal, []) or []),
            _number(target.get("calories", 0.0)),
        )

    calories = _round(sum(summary["calories"] for summary in meals.values()))
    protein = _round(sum(summary["protein_g"] for summary in meals.values()))
    carbs = _round(sum(summary["carbs_g"] for summary in meals.values()))
    fat = _round(sum(summary["fat_g"] for summary in meals.values()))
    planned = _number(daily_target_calories)
    return {
        "planned_calories": _round(planned),
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "calorie_delta": _round(calories - planned),
        "completion_ratio": _round(calories / planned) if planned > 0 else 0.0,
        "missing_required_slots": sum(
            summary["missing_required_slots"] for summary in meals.values()
        ),
        "meals": meals,
    }


def summarize_week(
    plan_data: Mapping[str, Mapping[str, list[Mapping[str, Any]]]],
    targets: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return day summaries derived from the persisted plan and current profile targets."""
    meal_targets = targets.get("meal_targets", {})
    daily_target = _number(targets.get("daily_calories", 0.0))
    return {
        str(day): summarize_day(day_plan or {}, meal_targets, daily_target)
        for day, day_plan in (plan_data or {}).items()
    }


def build_change_summary(
    *,
    day: str,
    meal: str,
    slot: str,
    before_totals: Mapping[str, Mapping[str, Any]],
    after_totals: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Describe the numeric effect of a single saved swap for the Flutter UI."""
    before_day = before_totals.get(day, {})
    after_day = after_totals.get(day, {})
    before_meal = before_day.get("meals", {}).get(meal, {})
    after_meal = after_day.get("meals", {}).get(meal, {})
    return {
        "day": day,
        "meal": meal,
        "slot": slot,
        "meal_calories_delta": _round(
            _number(after_meal.get("calories")) - _number(before_meal.get("calories"))
        ),
        "day_calories_delta": _round(
            _number(after_day.get("calories")) - _number(before_day.get("calories"))
        ),
        "protein_delta_g": _round(
            _number(after_day.get("protein_g")) - _number(before_day.get("protein_g"))
        ),
        "carbs_delta_g": _round(
            _number(after_day.get("carbs_g")) - _number(before_day.get("carbs_g"))
        ),
        "fat_delta_g": _round(
            _number(after_day.get("fat_g")) - _number(before_day.get("fat_g"))
        ),
    }
