from __future__ import annotations

from api.services.weekly_plan_totals import build_change_summary, summarize_week


TARGETS = {
    "daily_calories": 2000.0,
    "meal_targets": {
        "breakfast": {"calories": 500.0},
        "lunch": {"calories": 700.0},
        "dinner": {"calories": 600.0},
        "snack": {"calories": 200.0},
    },
}


def _item(
    *,
    slot: str,
    calories: float,
    protein: float,
    carbs: float,
    fat: float,
) -> dict:
    return {
        "slot": slot,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
    }


def test_weekly_totals_sum_servings_and_mark_missing_slots_without_inventing_values() -> None:
    plan = {
        "الأحد": {
            "breakfast": [
                _item(slot="نشويات", calories=250, protein=8, carbs=45, fat=4),
                _item(slot="فاكهة", calories=80, protein=1, carbs=20, fat=0),
            ],
            "lunch": [
                _item(slot="بروتين", calories=320, protein=36, carbs=6, fat=12),
                {"slot": "خضار", "missing": True, "calories": 999},
            ],
            "dinner": [],
            "snack": [],
        }
    }

    summary = summarize_week(plan, TARGETS)["الأحد"]

    assert summary["calories"] == 650.0
    assert summary["protein_g"] == 45.0
    assert summary["carbs_g"] == 71.0
    assert summary["fat_g"] == 16.0
    assert summary["calorie_delta"] == -1350.0
    assert summary["completion_ratio"] == 0.3
    assert summary["missing_required_slots"] == 1
    assert summary["meals"]["lunch"]["calories"] == 320.0
    assert summary["meals"]["lunch"]["missing_required_slots"] == 1
    assert summary["meals"]["dinner"]["calorie_delta"] == -600.0


def test_swap_change_summary_reflects_exact_before_after_meal_and_day_deltas() -> None:
    before_plan = {
        "الأحد": {
            "breakfast": [],
            "lunch": [
                _item(slot="بروتين", calories=220, protein=25, carbs=4, fat=9),
                _item(slot="نشويات", calories=280, protein=7, carbs=52, fat=3),
            ],
            "dinner": [],
            "snack": [],
        }
    }
    after_plan = {
        "الأحد": {
            "breakfast": [],
            "lunch": [
                _item(slot="بروتين", calories=280, protein=35, carbs=6, fat=12),
                _item(slot="نشويات", calories=280, protein=7, carbs=52, fat=3),
            ],
            "dinner": [],
            "snack": [],
        }
    }

    before_totals = summarize_week(before_plan, TARGETS)
    after_totals = summarize_week(after_plan, TARGETS)
    change = build_change_summary(
        day="الأحد",
        meal="lunch",
        slot="بروتين",
        before_totals=before_totals,
        after_totals=after_totals,
    )

    assert before_totals["الأحد"]["meals"]["lunch"]["calories"] == 500.0
    assert after_totals["الأحد"]["meals"]["lunch"]["calories"] == 560.0
    assert change == {
        "day": "الأحد",
        "meal": "lunch",
        "slot": "بروتين",
        "meal_calories_delta": 60.0,
        "day_calories_delta": 60.0,
        "protein_delta_g": 10.0,
        "carbs_delta_g": 2.0,
        "fat_delta_g": 3.0,
    }


def test_swap_change_summary_remains_zero_for_equivalent_portions() -> None:
    plan = {
        "الأحد": {
            "breakfast": [],
            "lunch": [_item(slot="بروتين", calories=250, protein=30, carbs=3, fat=8)],
            "dinner": [],
            "snack": [],
        }
    }
    totals = summarize_week(plan, TARGETS)

    change = build_change_summary(
        day="الأحد",
        meal="lunch",
        slot="بروتين",
        before_totals=totals,
        after_totals=totals,
    )

    assert change["meal_calories_delta"] == 0.0
    assert change["day_calories_delta"] == 0.0
    assert change["protein_delta_g"] == 0.0
    assert change["carbs_delta_g"] == 0.0
    assert change["fat_delta_g"] == 0.0
