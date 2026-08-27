from __future__ import annotations

from config import (
    CHARTS_DIR,
    DATASET_STATS_PATH,
    EVALUATION_RESULTS_PATH,
    PROCESSED_FOODS_PATH,
    RAW_COLLECTED_FOODS_PATH,
    RAW_EXTERNAL_DATA_DIR,
    RAW_LOCAL_FOODS_PATH,
    SYNTHETIC_USERS_PATH,
)


def test_organized_data_layers_keep_required_assets() -> None:
    assert RAW_LOCAL_FOODS_PATH.is_file()
    assert RAW_COLLECTED_FOODS_PATH.is_file()
    assert RAW_EXTERNAL_DATA_DIR.is_dir()
    assert len(list(RAW_EXTERNAL_DATA_DIR.glob("*.csv"))) == 5

    assert PROCESSED_FOODS_PATH.is_file()
    assert SYNTHETIC_USERS_PATH.is_file()
    assert DATASET_STATS_PATH.is_file()
    assert EVALUATION_RESULTS_PATH.is_file()
    assert CHARTS_DIR.is_dir()
    assert len(list(CHARTS_DIR.glob("*.png"))) == 13


def test_data_root_contains_only_documented_layers() -> None:
    data_dir = PROCESSED_FOODS_PATH.parents[1]
    assert not (data_dir / "foods_clean.csv").exists()
    assert not (data_dir / "foods_raw.csv").exists()
    assert not (data_dir / "local_food_source.csv").exists()
    assert not (data_dir / "synthetic_users.csv").exists()
    assert not (data_dir / "charts").exists()
    assert not (data_dir / "evaluation_results.csv").exists()
