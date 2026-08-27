from __future__ import annotations

import pandas as pd

from api.services.halal_policy import (
    ALCOHOL_REASON,
    PORK_REASON,
    apply_cultural_food_exclusions,
    explicit_non_halal_reasons,
)
from ml.core.meal_rules import apply_hard_filters


class _UserWithoutAdditionalRestrictions:
    dislikes: list[str] = []

    @staticmethod
    def get_health_flags() -> dict[str, object]:
        return {"allergies": []}


def test_explicit_non_halal_reasons_only_match_clear_indicators() -> None:
    assert explicit_non_halal_reasons("Pork loin, raw") == (PORK_REASON,)
    assert explicit_non_halal_reasons("Chicken cooked with wine") == (ALCOHOL_REASON,)
    assert explicit_non_halal_reasons("Pork cooked with beer") == (
        PORK_REASON,
        ALCOHOL_REASON,
    )
    assert explicit_non_halal_reasons("ترمس مسلوق") == ()
    assert explicit_non_halal_reasons("شاي أعشاب (مرمية/زعتر)") == ()
    assert explicit_non_halal_reasons("مشروب شعير خالي من الكحول") == ()


def test_cultural_exclusion_filters_dataframe_without_claiming_certification() -> None:
    foods = pd.DataFrame(
        [
            {"fdc_id": "1", "name": "Pork sausage"},
            {"fdc_id": "2", "name": "Sauce with wine"},
            {"fdc_id": "3", "name": "Chicken and rice"},
            {"fdc_id": "4", "name": "ترمس مسلوق"},
        ]
    )

    filtered = apply_cultural_food_exclusions(foods)

    assert filtered["fdc_id"].tolist() == ["3", "4"]


def test_meal_hard_filters_apply_cultural_exclusion_before_ranking() -> None:
    foods = pd.DataFrame(
        [
            {
                "fdc_id": "1",
                "name": "Pork rice bowl",
                "meal_type": "غداء",
                "category": "لحوم",
            },
            {
                "fdc_id": "2",
                "name": "Chicken rice bowl",
                "meal_type": "غداء",
                "category": "دواجن",
            },
            {
                "fdc_id": "3",
                "name": "Pasta with wine sauce",
                "meal_type": "غداء",
                "category": "نشويات",
            },
        ]
    )

    filtered = apply_hard_filters(foods, _UserWithoutAdditionalRestrictions(), meal="lunch")

    assert filtered["fdc_id"].tolist() == ["2"]
