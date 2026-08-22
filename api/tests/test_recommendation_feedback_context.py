"""Tests the bridge from explicit database feedback to recommendation context."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.db_models import CatalogSource, Food, User, UserFoodFeedback
from api.routes.recommendations import _user_dict


def make_user(email: str) -> User:
    return User(
        email=email,
        hashed_password="not-used-by-this-test",
        name=email,
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


def test_ready_feedback_context_uses_catalog_external_identifiers(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'feedback-context.db'}")
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()

    try:
        users = [make_user(f"context-{index}@example.com") for index in range(1, 4)]
        source = CatalogSource(code="context-source", name="Context", version="1")
        db.add_all([*users, source])
        db.commit()
        db.refresh(source)
        foods = [
            Food(
                source_id=source.id,
                external_id=f"CF-{index}",
                display_name=f"Food {index}",
                meal_tags=["lunch"],
                basis_grams=100.0,
                data_quality="verified",
                is_active=True,
            )
            for index in range(1, 5)
        ]
        db.add_all(foods)
        db.commit()

        db.add_all(
            [
                UserFoodFeedback(user_id=users[0].id, food_id=foods[0].id, event_type="like", score=1.0),
                UserFoodFeedback(user_id=users[0].id, food_id=foods[1].id, event_type="like", score=1.0),
                UserFoodFeedback(user_id=users[1].id, food_id=foods[0].id, event_type="like", score=1.0),
                UserFoodFeedback(user_id=users[1].id, food_id=foods[2].id, event_type="like", score=1.0),
                UserFoodFeedback(user_id=users[2].id, food_id=foods[1].id, event_type="like", score=1.0),
                UserFoodFeedback(user_id=users[2].id, food_id=foods[2].id, event_type="like", score=1.0),
                UserFoodFeedback(user_id=users[1].id, food_id=foods[3].id, event_type="save", score=0.5),
                UserFoodFeedback(user_id=users[2].id, food_id=foods[3].id, event_type="save", score=0.5),
                UserFoodFeedback(user_id=users[1].id, food_id=foods[1].id, event_type="save", score=0.5),
                UserFoodFeedback(user_id=users[2].id, food_id=foods[0].id, event_type="save", score=0.5),
            ]
        )
        db.commit()

        context = _user_dict(users[0], db)

        assert context["interaction_count"] == 2
        assert context["collaborative_signals_ready"] is True
        assert set(context["explicit_collaborative_scores"]) == {"CF-3", "CF-4"}
    finally:
        db.close()
        engine.dispose()
