"""Unit tests for the hybrid recommender's ranking-policy integration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_hybrid_module():
    spec = importlib.util.spec_from_file_location(
        "hybrid_recommender_under_test", PROJECT_ROOT / "09_hybrid_recommender.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StubModel:
    def __init__(self, scores: dict[str, float], score_column: str):
        self.scores = scores
        self.score_column = score_column

    def recommend(self, user, meal: str, top_k: int, exclude_ids=None):
        rows = []
        for index, (food_id, score) in enumerate(self.scores.items()):
            rows.append(
                {
                    "fdc_id": food_id,
                    "name": food_id,
                    "category": "اختبار",
                    "food_group": "بروتين",
                    "calories": 100.0,
                    "protein": 20.0,
                    "carbs": 5.0,
                    "fat": 2.0,
                    "fiber": 1.0,
                    "health_score": 75.0 + index,
                    self.score_column: score,
                }
            )
        return pd.DataFrame(rows)


class StubUser:
    def __init__(self, *, interaction_count: int, collaborative_signals_ready: bool):
        self.interaction_count = interaction_count
        self.collaborative_signals_ready = collaborative_signals_ready


def build_hybrid(*, cbf_weight: float = 0.6, cf_weight: float = 0.4):
    module = load_hybrid_module()
    recommender = module.HybridRecommender(
        cbf_weight=cbf_weight, cf_weight=cf_weight
    )
    recommender.cbf = StubModel(
        {"content-first": 0.95, "cf-first": 0.20}, "cbf_score"
    )
    recommender.cf = StubModel(
        {"content-first": 0.01, "cf-first": 0.99}, "cf_score"
    )
    return recommender


def test_hybrid_recommender_defaults_to_content_ranking_without_feedback() -> None:
    ranked = build_hybrid()._score_candidates(
        StubUser(interaction_count=100, collaborative_signals_ready=False), "lunch"
    )

    assert ranked.iloc[0]["fdc_id"] == "content-first"


def test_hybrid_recommender_uses_cf_only_after_feedback_is_declared_ready() -> None:
    ranked = build_hybrid(cbf_weight=0.4, cf_weight=0.6)._score_candidates(
        StubUser(interaction_count=5, collaborative_signals_ready=True), "lunch"
    )

    assert ranked.iloc[0]["fdc_id"] == "cf-first"
