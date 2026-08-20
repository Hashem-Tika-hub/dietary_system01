from types import SimpleNamespace

import pandas as pd

from api.services.recommendation_policy import (
    build_food_cluster_map,
    build_recommendation_reasons,
    select_diverse_candidate,
)


def _foods() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"fdc_id": "A", "calories": 95, "protein": 2, "carbs": 22, "fat": 0.5, "fiber": 3, "sugar": 10, "sodium": 5},
            {"fdc_id": "B", "calories": 102, "protein": 2.2, "carbs": 24, "fat": 0.4, "fiber": 3.1, "sugar": 11, "sodium": 4},
            {"fdc_id": "C", "calories": 330, "protein": 28, "carbs": 2, "fat": 22, "fiber": 0, "sugar": 0, "sodium": 70},
            {"fdc_id": "D", "calories": 320, "protein": 27, "carbs": 3, "fat": 21, "fiber": 0, "sugar": 0, "sodium": 75},
        ]
    )


def test_food_clusters_are_deterministic_and_cover_every_food() -> None:
    clusters_first = build_food_cluster_map(_foods(), n_clusters=2)
    clusters_second = build_food_cluster_map(_foods(), n_clusters=2)

    assert set(clusters_first) == {"A", "B", "C", "D"}
    assert clusters_first == clusters_second
    assert len(set(clusters_first.values())) == 2


def test_diversity_selection_prefers_fresh_cluster_without_removing_fallback() -> None:
    candidates = pd.DataFrame(
        [
            {"fdc_id": "top", "hybrid_score": 0.95, "food_cluster": 1},
            {"fdc_id": "fresh", "hybrid_score": 0.82, "food_cluster": 2},
            {"fdc_id": "other-used", "hybrid_score": 0.80, "food_cluster": 1},
        ]
    )

    selected = select_diverse_candidate(candidates, recently_used_clusters=[1])
    assert selected.candidate["fdc_id"] == "fresh"
    assert selected.diversity_applied is True

    fallback = select_diverse_candidate(candidates, recently_used_clusters=[1, 2])
    assert fallback.candidate["fdc_id"] == "top"
    assert fallback.diversity_applied is False


def test_recommendation_reason_explains_goal_meal_and_diversity() -> None:
    user = SimpleNamespace(goal="lose", has_diabetes=False, has_bp=False)
    candidate = pd.Series({"diabetic_friendly": False, "low_sodium": False})

    reasons = build_recommendation_reasons(
        user=user,
        meal="lunch",
        candidate=candidate,
        diversity_applied=True,
    )

    assert len(reasons) == 3
    assert "خفض السعرات" in reasons[0]
    assert "الغداء" in reasons[1]
    assert "تنوع" in reasons[2]
