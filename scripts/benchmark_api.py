"""Repeatable in-process API benchmark for local development only.

Measures FastAPI routing, validation, serialization, and SQLite access. It does
not include network latency, TLS, an external database, authentication token
verification, or serialized ML model inference.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "benchmark-only-secret-not-for-production")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.db_models import CatalogSource, Food, User
from api.dependencies import get_current_user
from api.routes.users import router as users_router

RUNS = 50
WARMUP_RUNS = 5


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def summarize(durations_ms: list[float], status_codes: list[int]) -> dict:
    return {
        "runs": len(durations_ms),
        "status_codes": sorted(set(status_codes)),
        "min_ms": round(min(durations_ms), 3),
        "mean_ms": round(statistics.fmean(durations_ms), 3),
        "median_ms": round(statistics.median(durations_ms), 3),
        "p95_ms": round(percentile(durations_ms, 0.95), 3),
        "p99_ms": round(percentile(durations_ms, 0.99), 3),
        "max_ms": round(max(durations_ms), 3),
    }


def benchmark(client: TestClient, method: str, path: str, *, json_body=None) -> dict:
    for _ in range(WARMUP_RUNS):
        response = client.request(method, path, json=json_body)
        response.raise_for_status()

    durations_ms: list[float] = []
    status_codes: list[int] = []
    for _ in range(RUNS):
        started = time.perf_counter_ns()
        response = client.request(method, path, json=json_body)
        durations_ms.append((time.perf_counter_ns() - started) / 1_000_000)
        status_codes.append(response.status_code)
        response.raise_for_status()

    return summarize(durations_ms, status_codes)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="dietary-api-benchmark-") as tmpdir:
        database_path = Path(tmpdir) / "benchmark.db"
        engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        db = session_factory()

        user = User(
            email="benchmark@example.com",
            hashed_password="not-used-in-benchmark",
            name="مستخدم قياس الأداء",
            age=30,
            gender="male",
            weight=75.0,
            height=175.0,
            activity_level=3,
            goal="maintain",
            allergies=[],
            dislikes=[],
            favorites=[],
        )
        source = CatalogSource(
            code="benchmark-source", name="Benchmark", version="1"
        )
        db.add_all([user, source])
        db.commit()
        db.refresh(user)
        db.refresh(source)
        feedback_food = Food(
            source_id=source.id,
            external_id="BENCHMARK-FOOD",
            display_name="طعام قياس الأداء",
            meal_tags=["lunch"],
            basis_grams=100.0,
            data_quality="verified",
            is_active=True,
        )
        db.add(feedback_food)
        db.commit()
        db.refresh(feedback_food)

        app = FastAPI()
        app.include_router(users_router)

        def override_db():
            yield db

        def override_current_user():
            return db.get(User, user.id)

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_current_user

        with TestClient(app) as client:
            results = {
                "measurement_scope": {
                    "environment": "FastAPI TestClient with local SQLite",
                    "runs_per_endpoint": RUNS,
                    "warmup_runs": WARMUP_RUNS,
                    "excluded": [
                        "network and TLS latency",
                        "external database latency",
                        "authentication token verification",
                        "serialized ML model inference",
                    ],
                },
                "endpoints": {
                    "GET /users/profile": benchmark(client, "GET", "/users/profile"),
                    "GET /users/meal-logs": benchmark(client, "GET", "/users/meal-logs"),
                    "GET /users/meal-logs/summary": benchmark(
                        client, "GET", "/users/meal-logs/summary"
                    ),
                    "POST /users/meal-logs": benchmark(
                        client,
                        "POST",
                        "/users/meal-logs",
                        json_body={
                            "meal_type": "lunch",
                            "food_name": "وجبة قياس",
                            "portion_g": 150,
                            "calories": 400,
                            "protein": 30,
                            "carbs": 40,
                            "fat": 10,
                        },
                    ),
                    "POST /users/food-feedback": benchmark(
                        client,
                        "POST",
                        "/users/food-feedback",
                        json_body={
                            "food_id": feedback_food.id,
                            "event_type": "like",
                        },
                    ),
                    "GET /users/food-feedback/readiness": benchmark(
                        client, "GET", "/users/food-feedback/readiness"
                    ),
                },
            }

        db.close()
        engine.dispose()

    output_dir = PROJECT_ROOT / "reports"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "api_benchmark_local.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
