"""Unit tests for calorie calculations and non-negotiable allergy safety."""

from __future__ import annotations

import pandas as pd
import pytest

import meal_rules
from recommender_engine import get_user_targets


class AllergyUser:
    def __init__(self, allergies: list[str]):
        self._allergies = allergies
        self.dislikes: list[str] = []

    def get_health_flags(self) -> dict:
        return {
            "allergies": self._allergies,
            "diabetic_friendly": False,
            "low_sodium": False,
            "low_fat": False,
        }


def _male_gain_profile() -> dict:
    return {
        "name": "calorie-test-user",
        "age": 30,
        "gender": "male",
        "weight": 80.0,
        "height": 180.0,
        "activity_level": 3,
        "goal": "gain",
        "allergies": [],
        "dislikes": [],
        "favorites": [],
    }


def test_daily_calorie_target_uses_bmr_activity_and_goal_adjustment() -> None:
    """Mifflin-St Jeor, activity factor, and goal adjustment stay traceable."""
    targets = get_user_targets(_male_gain_profile())

    # BMR = 10*80 + 6.25*180 - 5*30 + 5 = 1780.
    assert targets["bmr"] == 1780.0
    # TDEE = 1780 * 1.55 = 2759; gain goal adds 15%.
    assert targets["tdee"] == 2759.0
    assert targets["daily_calories"] == 3172.9
    assert targets["protein_g"] == 238.0
    assert targets["carbs_g"] == 396.6
    assert targets["fat_g"] == 70.5


def test_meal_calorie_distribution_preserves_daily_budget_with_rounding_bound() -> None:
    """Rounded meal targets follow the configured 25/35/30/10 distribution."""
    targets = get_user_targets(_male_gain_profile())
    meals = targets["meal_targets"]

    assert meals["breakfast"]["calories"] == 793.0
    assert meals["lunch"]["calories"] == 1111.0
    assert meals["dinner"]["calories"] == 952.0
    assert meals["snack"]["calories"] == 317.0

    rounded_total = sum(meal["calories"] for meal in meals.values())
    # Each meal is rounded to a whole calorie, so the total can differ by < 2 kcal.
    assert rounded_total == pytest.approx(targets["daily_calories"], abs=2.0)


def test_portion_calories_follow_target_or_safe_food_group_caps() -> None:
    portion_g, calories = meal_rules.compute_portion(200.0, 300.0, "بروتين")
    assert (portion_g, calories) == (150, 300)

    # Fat-dense foods must not exceed the small, explicit fat serving cap.
    portion_g, calories = meal_rules.compute_portion(10.0, 500.0, "دهون")
    assert (portion_g, calories) == (30, 3)

    # Missing or zero energy values cannot produce a division-by-zero portion.
    portion_g, calories = meal_rules.compute_portion(0.0, 250.0, "خضار")
    assert (portion_g, calories) == (80, 0)


def test_known_allergen_conflicts_are_blocked_for_mixed_catalog_formats() -> None:
    """Known allergens are removed before score-based ranking can use them."""
    candidates = pd.DataFrame(
        {
            "fdc_id": ["milk-score-99", "wheat-score-98", "egg-safe"],
            "meal_type": ["غداء", "غداء", "غداء"],
            "category": ["أطباق متنوعة", "أطباق متنوعة", "أطباق متنوعة"],
            "allergen_codes": [
                "ALLERGEN.MILK, allergen.soy",
                {"allergen.wheat"},
                ["allergen.egg"],
            ],
            "hybrid_score": [0.99, 0.98, 0.01],
        }
    )

    eligible = meal_rules.apply_hard_filters(
        candidates,
        AllergyUser([" allergen.MILK ", "جلوتين"]),
        meal="lunch",
    )

    assert eligible["fdc_id"].tolist() == ["egg-safe"]
    assert eligible["hybrid_score"].tolist() == [0.01]
