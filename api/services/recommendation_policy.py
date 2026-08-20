"""Pure, testable helpers for safe and explainable recommendation ranking.

Hard eligibility rules must run before every function that ranks candidates.
Collaborative scores remain disabled unless real, consented interaction signals
are explicitly available. Content-based ranking is the safe cold-start baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


FOOD_CLUSTER_FEATURES = (
    "calories",
    "protein",
    "carbs",
    "fat",
    "fiber",
    "sugar",
    "sodium",
)

GOAL_REASONS = {
    "lose": "مناسب لهدف خفض السعرات بصورة تدريجية.",
    "maintain": "مناسب لهدف المحافظة على الاحتياج التقريبي للطاقة.",
    "gain": "مناسب لهدف زيادة الكتلة والطاقة.",
    "sport": "مناسب لهدف النشاط والأداء الرياضي.",
}

MEAL_REASONS = {
    "breakfast": "يتوافق مع قالب الفطور وحصته المقترحة.",
    "lunch": "يتوافق مع قالب الغداء وحصته المقترحة.",
    "dinner": "يتوافق مع قالب العشاء وحصته المقترحة.",
    "snack": "يتوافق مع قالب الوجبة الخفيفة وحصتها المقترحة.",
}


@dataclass(frozen=True)
class HybridWeights:
    """Normalized weights used to blend content and collaborative scores."""

    content: float
    collaborative: float


@dataclass(frozen=True)
class DiversitySelection:
    """A selected candidate and whether a fresher food cluster was used."""

    candidate: pd.Series
    diversity_applied: bool


def effective_hybrid_weights(
    *,
    configured_content_weight: float,
    configured_collaborative_weight: float,
    interaction_count: int = 0,
    collaborative_signals_ready: bool = False,
    minimum_interactions: int = 5,
) -> HybridWeights:
    """Return safe hybrid weights for the available evidence.

    Collaborative scores are intentionally disabled unless the application has
    real, consented feedback signals and enough observations. Meal-log count by
    itself does not enable collaborative ranking; callers must explicitly set
    ``collaborative_signals_ready`` after a proper feedback pipeline exists.
    """

    if configured_content_weight < 0 or configured_collaborative_weight < 0:
        raise ValueError("Hybrid weights cannot be negative")
    if configured_content_weight + configured_collaborative_weight <= 0:
        raise ValueError("At least one configured hybrid weight must be positive")
    if interaction_count < 0:
        raise ValueError("interaction_count cannot be negative")

    if not collaborative_signals_ready or interaction_count < minimum_interactions:
        return HybridWeights(content=1.0, collaborative=0.0)

    total = configured_content_weight + configured_collaborative_weight
    return HybridWeights(
        content=configured_content_weight / total,
        collaborative=configured_collaborative_weight / total,
    )


def min_max_normalize(scores: pd.Series) -> pd.Series:
    """Normalize scores safely, including empty and constant series."""

    numeric = pd.to_numeric(scores, errors="coerce").fillna(0.0)
    if numeric.empty:
        return numeric.astype(float)

    minimum = numeric.min()
    maximum = numeric.max()
    if maximum == minimum:
        return pd.Series(0.5, index=numeric.index, dtype=float)
    return (numeric - minimum) / (maximum - minimum)


def blend_candidate_scores(
    candidates: pd.DataFrame,
    *,
    content_column: str = "raw_cbf",
    collaborative_column: str = "raw_cf",
    weights: HybridWeights,
) -> pd.DataFrame:
    """Add normalized score columns and a deterministic ``hybrid_score``.

    The function performs no filtering. Hard eligibility rules must be applied
    before this stage so a high score can never override a safety constraint.
    """

    if content_column not in candidates.columns:
        raise ValueError(f"Missing required content score column: {content_column}")

    ranked = candidates.copy()
    ranked["cbf_norm"] = min_max_normalize(ranked[content_column])

    if collaborative_column in ranked.columns:
        ranked["cf_norm"] = min_max_normalize(ranked[collaborative_column])
    else:
        ranked["cf_norm"] = 0.0

    ranked["hybrid_score"] = (
        weights.content * ranked["cbf_norm"]
        + weights.collaborative * ranked["cf_norm"]
    )
    return ranked.sort_values("hybrid_score", ascending=False).reset_index(drop=True)


def build_food_cluster_map(
    foods: pd.DataFrame,
    *,
    id_column: str = "fdc_id",
    n_clusters: int = 6,
) -> dict[str, int]:
    """Cluster foods by nutrient profile for weekly-plan diversity.

    This is an unsupervised food-catalog analysis only. It never determines
    safety or medical suitability and must run after the catalog is curated.
    """

    if id_column not in foods.columns:
        raise ValueError(f"Missing food identifier column: {id_column}")
    if n_clusters < 2:
        raise ValueError("n_clusters must be at least 2")

    available = [column for column in FOOD_CLUSTER_FEATURES if column in foods.columns]
    if len(available) < 2:
        raise ValueError("At least two numeric nutrient features are required")

    rows = foods.drop_duplicates(subset=[id_column]).copy()
    if len(rows) < 2:
        return {str(row[id_column]): 0 for _, row in rows.iterrows()}

    cluster_count = min(n_clusters, len(rows))
    matrix = rows[available].apply(pd.to_numeric, errors="coerce")
    matrix = matrix.fillna(matrix.median(numeric_only=True)).fillna(0.0)
    scaled = StandardScaler().fit_transform(matrix)
    labels = KMeans(n_clusters=cluster_count, random_state=42, n_init=20).fit_predict(scaled)

    return {str(food_id): int(label) for food_id, label in zip(rows[id_column], labels)}


def select_diverse_candidate(
    candidates: pd.DataFrame,
    *,
    recently_used_clusters: Iterable[int] = (),
    score_column: str = "hybrid_score",
    cluster_column: str = "food_cluster",
) -> DiversitySelection:
    """Choose the highest-ranked candidate from a fresh cluster when possible.

    The function does not discard candidates permanently. If every eligible
    candidate belongs to a recently used nutrient cluster, it falls back to the
    highest-ranked candidate and reports that diversity was not applied.
    """

    if candidates.empty:
        raise ValueError("Cannot select from an empty candidate set")
    if score_column not in candidates.columns:
        raise ValueError(f"Missing score column: {score_column}")

    ranked = candidates.sort_values(score_column, ascending=False).reset_index(drop=True)
    top = ranked.iloc[0]
    if cluster_column not in ranked.columns:
        return DiversitySelection(candidate=top, diversity_applied=False)

    used = {int(cluster) for cluster in recently_used_clusters if pd.notna(cluster)}
    fresh = ranked[~ranked[cluster_column].isin(used)]
    if fresh.empty:
        return DiversitySelection(candidate=top, diversity_applied=False)

    selected = fresh.iloc[0]
    return DiversitySelection(
        candidate=selected,
        diversity_applied=bool(selected.name != top.name),
    )


def build_recommendation_reasons(
    *,
    user,
    meal: str,
    candidate: pd.Series,
    diversity_applied: bool = False,
) -> list[str]:
    """Return concise, non-diagnostic reasons for an already eligible item."""

    reasons = [
        GOAL_REASONS.get(getattr(user, "goal", ""), "يتوافق مع هدف المستخدم المعلن."),
        MEAL_REASONS.get(meal, "يتوافق مع قالب الوجبة وحصتها المقترحة."),
    ]

    if bool(getattr(user, "has_diabetes", False)) and bool(candidate.get("diabetic_friendly", False)):
        reasons.append("يتوافق مع الفلتر الغذائي المعلن للسكر.")
    elif bool(getattr(user, "has_bp", False)) and bool(candidate.get("low_sodium", False)):
        reasons.append("يتوافق مع الفلتر الغذائي المعلن للصوديوم.")
    elif diversity_applied:
        reasons.append("اختير لتعزيز تنوع الخطة الأسبوعية عن أصناف غذائية متشابهة.")
    else:
        reasons.append("يتوافق مع خصائص المغذيات المستهدفة للوجبة.")

    return reasons


def ranking_basis(weights: HybridWeights) -> str:
    """Return a stable, user-facing explanation label for the active policy."""

    if weights.collaborative == 0:
        return "content_based"
    return "hybrid"
