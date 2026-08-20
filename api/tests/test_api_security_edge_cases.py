from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.auth import create_token
from api.database import Base, get_db
from api.db_models import User
from api.routes.users import router as users_router
from api.schemas import UserRegister


@pytest.fixture()
def secured_client_and_user(tmp_path) -> Generator[tuple[TestClient, User, Session], None, None]:
    """Provide a real protected users router without overriding JWT validation."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'security-edge-cases.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()

    user = User(
        email="security-edge@example.com",
        hashed_password="not-used-by-route-tests",
        name="مستخدم أمان الاختبار",
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

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as client:
        yield client, user, db

    db.close()
    engine.dispose()


def auth_headers(user: User) -> dict[str, str]:
    token = create_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("payload", "field", "original_value"),
    [
        ({"age": 0}, "age", 28),
        ({"age": -1}, "age", 28),
        ({"age": 101}, "age", 28),
        ({"age": 999}, "age", 28),
        ({"weight": 0}, "weight", 75.0),
        ({"weight": -0.1}, "weight", 75.0),
        ({"height": 0}, "height", 175.0),
        ({"height": -10}, "height", 175.0),
        ({"activity_level": 0}, "activity_level", 3),
        ({"activity_level": -1}, "activity_level", 3),
    ],
)
def test_profile_rejects_zero_or_negative_body_measurements(
    secured_client_and_user,
    payload: dict[str, int | float],
    field: str,
    original_value: int | float,
) -> None:
    """Pydantic must reject invalid profile updates before persistence."""
    client, user, db = secured_client_and_user

    response = client.put("/users/profile", json=payload, headers=auth_headers(user))

    assert response.status_code == 422
    assert any(error["loc"][-1] == field for error in response.json()["detail"])
    db.refresh(user)
    assert getattr(user, field) == original_value


def test_partial_profile_update_rejects_an_implausible_combined_body_profile(
    secured_client_and_user,
) -> None:
    """A partial update must be checked against the stored height or weight."""
    client, user, db = secured_client_and_user

    response = client.put(
        "/users/profile",
        json={"weight": 30},
        headers=auth_headers(user),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "تركيبة الوزن والطول غير منطقية؛ راجع البيانات المدخلة"
    db.refresh(user)
    assert user.weight == 75.0


def test_new_user_model_rejects_an_implausible_combined_body_profile() -> None:
    """Registration validation rejects an extreme weight/height combination."""
    with pytest.raises(ValidationError, match="تركيبة الوزن والطول غير منطقية"):
        UserRegister(
            email="invalid-profile@example.com",
            password="secret123",
            name="مستخدم اختبار",
            age=25,
            gender="male",
            weight=30,
            height=200,
        )


def test_profile_update_accepts_a_valid_boundary_combination(secured_client_and_user) -> None:
    """Sanity checks must not reject a complete profile that remains in range."""
    client, user, _ = secured_client_and_user

    response = client.put(
        "/users/profile",
        json={"age": 100, "weight": 30, "height": 170},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["age"] == 100
    assert response.json()["weight"] == 30.0
    assert response.json()["height"] == 170.0


def test_protected_profile_rejects_a_missing_jwt(secured_client_and_user) -> None:
    """A protected endpoint must fail at the HTTP bearer boundary without a token."""
    client, _, _ = secured_client_and_user

    response = client.get("/users/profile")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_protected_profile_rejects_an_expired_jwt(secured_client_and_user) -> None:
    """An otherwise valid but expired token must never reach route logic."""
    client, user, _ = secured_client_and_user
    expired_token = create_token(
        {"sub": str(user.id)}, expires_delta=timedelta(seconds=-1)
    )

    response = client.get(
        "/users/profile",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "رمز المصادقة غير صالح أو منتهي الصلاحية"
