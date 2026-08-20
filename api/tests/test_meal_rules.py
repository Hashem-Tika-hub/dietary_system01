"""Unit tests for hard eligibility rules used before recommendation ranking."""

from __future__ import annotations

import pandas as pd

import meal_rules


class StubUser:
    def __init__(self, *, allergies=None, dislikes=None):
        self._allergies = allergies or []
        self.dislikes = dislikes or []

    def get_health_flags(self) -> dict:
        return {
            "allergies": self._allergies,
            "diabetic_friendly": False,
            "low_sodium": False,
            "low_fat": False,
        }


def test_canonical_allergen_codes_are_excluded_before_ranking() -> None:
    candidates = pd.DataFrame(
        {
            "fdc_id": ["milk-dish", "safe-dish"],
            "meal_type": ["غداء", "غداء"],
            "category": ["أطباق متنوعة", "أطباق متنوعة"],
            "allergen_codes": [["allergen.milk"], []],
        }
    )

    eligible = meal_rules.apply_hard_filters(
        candidates, StubUser(allergies=["allergen.milk"]), meal="lunch"
    )

    assert eligible["fdc_id"].tolist() == ["safe-dish"]


def test_legacy_category_allergy_fallback_remains_supported() -> None:
    candidates = pd.DataFrame(
        {
            "fdc_id": ["nuts", "fruit"],
            "meal_type": ["سناك", "سناك"],
            "category": ["مكسرات", "فواكه"],
        }
    )

    eligible = meal_rules.apply_hard_filters(
        candidates, StubUser(allergies=["مكسرات"]), meal="snack"
    )

    assert eligible["fdc_id"].tolist() == ["fruit"]


def test_hard_filter_applies_meal_eligibility_before_candidates_are_ranked() -> None:
    candidates = pd.DataFrame(
        {
            "fdc_id": ["breakfast-only", "lunch-ok"],
            "meal_type": ["فطور", "غداء، عشاء"],
            "category": ["فواكه", "فواكه"],
        }
    )

    eligible = meal_rules.apply_hard_filters(candidates, StubUser(), meal="lunch")

    assert eligible["fdc_id"].tolist() == ["lunch-ok"]


def test_multiple_allergies_filter_known_conflicts_when_catalog_data_is_incomplete() -> None:
    """Known milk/nut conflicts are excluded while incomplete safe rows do not crash.

    The catalog deliberately contains a canonical allergy code, a comma-delimited
    code, a legacy category-only row, and a row without allergy metadata.
    """
    candidates = pd.DataFrame(
        {
            "fdc_id": [
                "milk-with-code",
                "peanut-with-code",
                "legacy-nut-category",
                "safe-row-with-missing-allergen-data",
            ],
            "meal_type": ["غداء", "غداء", "غداء", "غداء"],
            "category": ["أطباق متنوعة", "أطباق متنوعة", "مكسرات", "فواكه"],
            "allergen_codes": [
                ["allergen.milk"],
                "allergen.peanut, allergen.soy",
                None,
                None,
            ],
        }
    )

    eligible = meal_rules.apply_hard_filters(
        candidates,
        StubUser(allergies=["حليب", "مكسرات"]),
        meal="lunch",
    )

    assert eligible["fdc_id"].tolist() == ["safe-row-with-missing-allergen-data"]
    assert len(eligible) == 1
    assert candidates["allergen_codes"].isna().sum() == 2
