"""API integration tests for user profile and meal-log management routes."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base, get_db
from api.db_models import User
from api.dependencies import get_current_user
from api.routes.users import router as users_router


@pytest.fixture()
def client_and_db(tmp_path) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    user = User(
        email="api-test@example.com",
        hashed_password="not-used-by-this-route-test",
        name="مستخدم الاختبار",
        age=28,
        gender="male",
        weight=75.0,
        height=175.0,
        activity_level=3,
        goal="maintain",
        allergies=[],
        dislikes=[],
        favorites=[],
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app = FastAPI()
    app.include_router(users_router)

    def override_db():
        yield db

    def override_current_user():
        return db.get(User, user.id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        yield client, db

    db.close()
    engine.dispose()


def test_meal_log_crud_and_summary(client_and_db) -> None:
    client, _ = client_and_db
    payload = {
        "meal_type": "lunch",
        "food_name": "وجبة اختبار",
        "fdc_id": "TEST-FOOD-1",
        "portion_g": 150,
        "calories": 320,
        "protein": 25,
        "carbs": 35,
        "fat": 9,
        "notes": "اختبار API",
    }

    created = client.post("/users/meal-logs", json=payload)
    assert created.status_code == 201
    log_id = created.json()["id"]

    fetched = client.get(f"/users/meal-logs/{log_id}")
    assert fetched.status_code == 200
    assert fetched.json()["food_name"] == "وجبة اختبار"

    updated = client.patch(
        f"/users/meal-logs/{log_id}", json={"calories": 350, "notes": "محدث"}
    )
    assert updated.status_code == 200
    assert updated.json()["calories"] == 350
    assert updated.json()["notes"] == "محدث"

    summary = client.get("/users/meal-logs/summary")
    assert summary.status_code == 200
    assert summary.json() == {
        "count": 1,
        "calories": 350.0,
        "protein": 25.0,
        "carbs": 35.0,
        "fat": 9.0,
    }

    deleted = client.delete(f"/users/meal-logs/{log_id}")
    assert deleted.status_code == 204
    assert client.get(f"/users/meal-logs/{log_id}").status_code == 404


def test_profile_update_validates_and_persists_current_user(client_and_db) -> None:
    client, _ = client_and_db

    response = client.put(
        "/users/profile",
        json={"weight": 72.5, "goal": "lose", "favorites": ["بقوليات"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["weight"] == 72.5
    assert body["goal"] == "lose"
    assert body["favorites"] == ["بقوليات"]
