"""Audit the project datasets for ML-readiness without training or loading models."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED_FOODS_PATH = DATA / "processed" / "foods_clean.csv"
SYNTHETIC_USERS_PATH = DATA / "fixtures" / "synthetic_users.csv"
EVALUATION_RESULTS_PATH = DATA / "outputs" / "evaluations" / "evaluation_results.csv"
OUT = ROOT / "reports" / "ml_dataset_audit.json"


def safe_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path, encoding="utf-8-sig")


def frame_summary(df: pd.DataFrame | None, name: str) -> dict:
    if df is None:
        return {"present": False}
    return {
        "present": True,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "missing_by_column": {k: int(v) for k, v in df.isna().sum().to_dict().items() if v},
        "duplicate_rows": int(df.duplicated().sum()),
    }


def sqlite_summary(path: Path) -> dict:
    if not path.exists():
        return {"present": False}
    with sqlite3.connect(path) as conn:
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
            conn,
        )["name"].tolist()
        counts = {}
        for table in tables:
            counts[table] = int(pd.read_sql_query(f'SELECT COUNT(*) AS n FROM "{table}"', conn).iloc[0, 0])
    return {"present": True, "tables": tables, "row_counts": counts}


def main() -> None:
    foods = safe_csv(PROCESSED_FOODS_PATH)
    users = safe_csv(SYNTHETIC_USERS_PATH)
    evaluation = safe_csv(EVALUATION_RESULTS_PATH)

    report = {
        "foods": frame_summary(foods, "foods_clean"),
        "synthetic_users": frame_summary(users, "synthetic_users"),
        "evaluation_results": frame_summary(evaluation, "evaluation_results"),
        "sqlite": sqlite_summary(DATA / "dietary.db"),
        "supervised_learning_readiness": {},
        "collaborative_filtering_readiness": {},
    }

    if foods is not None:
        report["foods"].update(
            {
                "unique_food_ids": int(foods["fdc_id"].nunique()) if "fdc_id" in foods else None,
                "category_distribution": {str(k): int(v) for k, v in foods.get("category", pd.Series(dtype=str)).value_counts().to_dict().items()},
                "nutrient_columns": [c for c in ["calories", "protein", "carbs", "fat", "fiber", "sugar", "sodium"] if c in foods.columns],
            }
        )

    if users is not None:
        feature_columns = [
            "age", "gender", "weight", "height", "activity_level", "goal",
            "has_diabetes", "has_bp", "has_cholesterol", "allergies", "dislikes", "favorites",
        ]
        derived_columns = ["bmi", "bmr", "tdee", "daily_calories", "protein_g", "carbs_g", "fat_g"]
        user_summary = report["synthetic_users"]
        user_summary.update(
            {
                "named_as_synthetic": True,
                "feature_columns_available": [c for c in feature_columns if c in users.columns],
                "derived_target_like_columns": [c for c in derived_columns if c in users.columns],
                "unique_users": int(users["name"].nunique()) if "name" in users else None,
                "goal_distribution": {str(k): int(v) for k, v in users.get("goal", pd.Series(dtype=str)).value_counts().to_dict().items()},
                "health_flag_counts": {
                    c: int(users[c].fillna(False).astype(bool).sum())
                    for c in ["has_diabetes", "has_bp", "has_cholesterol"]
                    if c in users
                },
            }
        )
        report["supervised_learning_readiness"] = {
            "has_feature_rows": bool(len(users)),
            "has_explicit_expert_label": False,
            "has_outcome_label": False,
            "target_like_values_are_formula_derived": True,
            "assessment": "not_ready_for_valid_supervised_personal-nutrition training",
        }

    db_counts = report["sqlite"].get("row_counts", {})
    explicit_feedback_rows = db_counts.get("user_food_feedback", 0)
    report["collaborative_filtering_readiness"] = {
        "stored_explicit_feedback_rows": explicit_feedback_rows,
        "has_real_user_item_interactions": explicit_feedback_rows > 0,
        "assessment": "cold_start_without_collected_explicit_feedback" if explicit_feedback_rows == 0 else "requires_distribution_and_quality_review",
    }

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
