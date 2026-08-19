"""Pure, testable ranking policy for meal recommendations.

The current collaborative model is trained from synthetic ratings. Therefore its
score must not influence production ranking until real, consented interaction
signals are explicitly available. Content-based ranking remains the safe
cold-start baseline.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class HybridWeights:
    """Normalized weights used to blend content and collaborative scores."""

    content: float
    collaborative: float


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


def ranking_basis(weights: HybridWeights) -> str:
    """Return a stable, user-facing explanation label for the active policy."""

    if weights.collaborative == 0:
        return "content_based"
    return "hybrid"
