"""Unit tests for ranking policy without loading serialized ML models."""

from __future__ import annotations

import pandas as pd
import pytest

from api.services.recommendation_policy import (
    HybridWeights,
    blend_candidate_scores,
    effective_hybrid_weights,
    min_max_normalize,
    ranking_basis,
)


def test_collaborative_weight_is_disabled_without_real_feedback() -> None:
    weights = effective_hybrid_weights(
        configured_content_weight=0.6,
        configured_collaborative_weight=0.4,
        interaction_count=100,
        collaborative_signals_ready=False,
    )

    assert weights == HybridWeights(content=1.0, collaborative=0.0)
    assert ranking_basis(weights) == "content_based"


def test_configured_weights_are_normalized_when_feedback_is_ready() -> None:
    weights = effective_hybrid_weights(
        configured_content_weight=3.0,
        configured_collaborative_weight=1.0,
        interaction_count=5,
        collaborative_signals_ready=True,
    )

    assert weights == HybridWeights(content=0.75, collaborative=0.25)
    assert ranking_basis(weights) == "hybrid"


def test_negative_or_empty_weights_are_rejected() -> None:
    with pytest.raises(ValueError):
        effective_hybrid_weights(
            configured_content_weight=-0.1,
            configured_collaborative_weight=1.1,
        )
    with pytest.raises(ValueError):
        effective_hybrid_weights(
            configured_content_weight=0.0,
            configured_collaborative_weight=0.0,
        )


def test_content_only_ranking_ignores_high_synthetic_cf_score() -> None:
    candidates = pd.DataFrame(
        {
            "fdc_id": ["content-first", "synthetic-cf-first"],
            "raw_cbf": [0.95, 0.20],
            "raw_cf": [0.01, 0.99],
        }
    )

    ranked = blend_candidate_scores(
        candidates,
        weights=HybridWeights(content=1.0, collaborative=0.0),
    )

    assert ranked.iloc[0]["fdc_id"] == "content-first"
    assert ranked.iloc[0]["hybrid_score"] == pytest.approx(1.0)


def test_hybrid_ranking_uses_both_available_signals() -> None:
    candidates = pd.DataFrame(
        {
            "fdc_id": ["content-first", "collaborative-first"],
            "raw_cbf": [0.95, 0.20],
            "raw_cf": [0.01, 0.99],
        }
    )

    ranked = blend_candidate_scores(
        candidates,
        weights=HybridWeights(content=0.4, collaborative=0.6),
    )

    assert ranked.iloc[0]["fdc_id"] == "collaborative-first"
    assert set(ranked.columns) >= {"cbf_norm", "cf_norm", "hybrid_score"}


def test_normalization_handles_constant_scores() -> None:
    normalized = min_max_normalize(pd.Series([7.0, 7.0]))
    assert normalized.tolist() == [0.5, 0.5]
