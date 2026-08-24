from __future__ import annotations

from copy import deepcopy
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base, get_db
from api.db_models import User, WeeklyPlan
from api.dependencies import get_current_user
from api.routes import recommendations as recommendation_routes


TARGETS = {
    "daily_calories": 2000.0,
    "meal_targets": {
        "breakfast": {"calories": 500.0},
        "lunch": {"calories": 700.0},
        "dinner": {"calories": 600.0},
        "snack": {"calories": 200.0},
    },
}


def _item(slot: str, calories: float, protein: float, carbs: float, fat: float) -> dict:
    return {
        "fdc_id": f"{slot}-{calories}",
        "slot": slot,
        "name": slot,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
    }


@pytest.fixture()
def client_and_db(tmp_path) -> Generator[tuple[TestClient, Session, User, WeeklyPlan], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'weekly-plan-swap.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    user = User(
        email="weekly-plan@example.com",
        hashed_password="not-used",
        name="مستخدم الخطة",
        age=30,
        gender="male",
        weight=75.0,
        height=175.0,
        activity_level=2,
        goal="maintain",
        allergies=[],
        dislikes=[],
        favorites=[],
    )
    plan = WeeklyPlan(
        user=user,
        plan_data={
            "الأحد": {
                "breakfast": [],
                "lunch": [
                    _item("بروتين", 220.0, 25.0, 4.0, 9.0),
                    _item("نشويات", 280.0, 7.0, 52.0, 3.0),
                ],
                "dinner": [],
                "snack": [],
            }
        },
    )
    db.add_all([user, plan])
    db.commit()
    db.refresh(user)
    db.refresh(plan)

    app = FastAPI()
    app.include_router(recommendation_routes.router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, user.id)

    with TestClient(app) as client:
        yield client, db, user, plan

    db.close()
    engine.dispose()


def test_weekly_swap_returns_and_persists_recalculated_totals(
    client_and_db, monkeypatch
) -> None:
    client, db, _, plan = client_and_db

    def fake_swap(plan_data, day, meal, slot, new_fdc_id, user_data):
        assert (day, meal, slot, new_fdc_id) == ("الأحد", "lunch", "بروتين", "new-protein")
        updated = deepcopy(plan_data)
        updated[day][meal][0] = _item("بروتين", 280.0, 35.0, 6.0, 12.0)
        updated[day][meal][0]["fdc_id"] = new_fdc_id
        return updated

    monkeypatch.setattr(recommendation_routes.engine, "get_user_targets", lambda _: TARGETS)
    monkeypatch.setattr(recommendation_routes.engine, "swap_meal_item", fake_swap)

    response = client.post(
        "/recommendations/weekly/swap",
        json={
            "plan_id": plan.id,
            "day": "الأحد",
            "meal": "lunch",
            "slot": "بروتين",
            "new_fdc_id": "new-protein",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["الأحد"]["lunch"][0]["fdc_id"] == "new-protein"
    assert payload["totals"]["الأحد"]["meals"]["lunch"]["calories"] == 560.0
    assert payload["totals"]["الأحد"]["calories"] == 560.0
    assert payload["change_summary"] == {
        "day": "الأحد",
        "meal": "lunch",
        "slot": "بروتين",
        "meal_calories_delta": 60.0,
        "day_calories_delta": 60.0,
        "protein_delta_g": 10.0,
        "carbs_delta_g": 2.0,
        "fat_delta_g": 3.0,
    }
    assert db.get(WeeklyPlan, plan.id).plan_data["الأحد"]["lunch"][0]["fdc_id"] == "new-protein"
