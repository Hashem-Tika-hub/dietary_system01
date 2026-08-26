from __future__ import annotations

import importlib.util
from pathlib import Path

from ml.core.cbf_model import ContentBasedFilter
from ml.core.hybrid_recommender import HybridRecommender
from ml.core.user_profiler import UserProfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_legacy_module(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recommender_engine_uses_ml_core_operational_types() -> None:
    import recommender_engine

    assert recommender_engine.UserProfile is UserProfile
    assert recommender_engine.ContentBasedFilter is ContentBasedFilter
    assert recommender_engine.HybridRecommender is HybridRecommender


def test_legacy_ml_modules_are_small_compatibility_exports() -> None:
    legacy_profile = _load_legacy_module("05_user_profiler.py", "legacy_profile")
    legacy_cbf = _load_legacy_module("07_cbf_model.py", "legacy_cbf")
    legacy_hybrid = _load_legacy_module("09_hybrid_recommender.py", "legacy_hybrid")

    assert legacy_profile.UserProfile is UserProfile
    assert legacy_cbf.ContentBasedFilter is ContentBasedFilter
    assert legacy_hybrid.HybridRecommender is HybridRecommender
    assert (PROJECT_ROOT / "05_user_profiler.py").stat().st_size < 500
    assert (PROJECT_ROOT / "07_cbf_model.py").stat().st_size < 500
    assert (PROJECT_ROOT / "09_hybrid_recommender.py").stat().st_size < 500
