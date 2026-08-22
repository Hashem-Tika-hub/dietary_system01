"""Unit tests for explicit-feedback collaborative filtering."""

from __future__ import annotations

import pytest

from api.services.feedback_collaborative_filter import (
    ExplicitFeedbackCollaborativeFilter,
    FeedbackRecord,
)


def test_filter_stays_in_cold_start_without_enough_explicit_feedback() -> None:
    model = ExplicitFeedbackCollaborativeFilter().fit(
        [
            FeedbackRecord(user_id=1, food_id=10, score=1.0),
            FeedbackRecord(user_id=1, food_id=11, score=0.5),
        ]
    )

    readiness = model.readiness_for(1)

    assert readiness.ready is False
    assert readiness.reason == "not_enough_explicit_feedback"
    assert model.score_unseen_foods(1) == {}


def test_filter_scores_only_unseen_foods_after_dataset_is_ready() -> None:
    records = [
        FeedbackRecord(user_id=1, food_id=10, score=1.0),
        FeedbackRecord(user_id=1, food_id=11, score=1.0),
        FeedbackRecord(user_id=2, food_id=10, score=1.0),
        FeedbackRecord(user_id=2, food_id=12, score=1.0),
        FeedbackRecord(user_id=3, food_id=11, score=1.0),
        FeedbackRecord(user_id=3, food_id=12, score=1.0),
    ]
    model = ExplicitFeedbackCollaborativeFilter(
        minimum_interactions=6,
        minimum_users=3,
        minimum_foods=3,
        minimum_target_user_interactions=2,
    ).fit(records)

    readiness = model.readiness_for(1)
    scores = model.score_unseen_foods(1)

    assert readiness.ready is True
    assert readiness.reason == "ready"
    assert 10 not in scores
    assert 11 not in scores
    assert scores[12] == pytest.approx(1.0)


def test_filter_rejects_out_of_contract_scores() -> None:
    with pytest.raises(ValueError, match="Feedback scores"):
        ExplicitFeedbackCollaborativeFilter().fit(
            [FeedbackRecord(user_id=1, food_id=10, score=0.75)]
        )
