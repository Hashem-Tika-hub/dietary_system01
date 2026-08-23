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


def test_filter_prefers_food_supported_by_more_similar_users() -> None:
    """The highest recommendation must reflect shared positive explicit signals."""
    records = [
        FeedbackRecord(user_id=1, food_id=10, score=1.0),
        FeedbackRecord(user_id=1, food_id=11, score=1.0),
        FeedbackRecord(user_id=2, food_id=10, score=1.0),
        FeedbackRecord(user_id=2, food_id=12, score=1.0),
        FeedbackRecord(user_id=2, food_id=13, score=1.0),
        FeedbackRecord(user_id=3, food_id=10, score=1.0),
        FeedbackRecord(user_id=3, food_id=12, score=1.0),
    ]
    model = ExplicitFeedbackCollaborativeFilter(
        minimum_interactions=7,
        minimum_users=3,
        minimum_foods=4,
        minimum_target_user_interactions=2,
    ).fit(records)

    scores = model.score_unseen_foods(1)

    assert scores[12] == pytest.approx(1.0)
    assert scores[12] > scores[13]
    assert set(scores).isdisjoint({10, 11})
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_filter_never_recommends_a_food_with_only_negative_neighbor_support() -> None:
    records = [
        FeedbackRecord(user_id=1, food_id=10, score=1.0),
        FeedbackRecord(user_id=1, food_id=11, score=1.0),
        FeedbackRecord(user_id=2, food_id=10, score=1.0),
        FeedbackRecord(user_id=2, food_id=12, score=1.0),
        FeedbackRecord(user_id=2, food_id=13, score=-1.0),
        FeedbackRecord(user_id=3, food_id=11, score=1.0),
        FeedbackRecord(user_id=3, food_id=12, score=1.0),
        FeedbackRecord(user_id=3, food_id=14, score=1.0),
    ]
    model = ExplicitFeedbackCollaborativeFilter(
        minimum_interactions=8,
        minimum_users=3,
        minimum_foods=5,
        minimum_target_user_interactions=2,
    ).fit(records)

    scores = model.score_unseen_foods(1)

    assert 12 in scores
    assert 13 not in scores
    assert set(scores).isdisjoint({10, 11})


def test_filter_is_deterministic_for_the_same_explicit_feedback() -> None:
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

    first = model.score_unseen_foods(1)
    second = model.score_unseen_foods(1)

    assert first == second
    assert first == {12: pytest.approx(1.0)}


def test_filter_returns_no_scores_when_ready_users_have_no_positive_similarity() -> None:
    records = [
        FeedbackRecord(user_id=1, food_id=10, score=1.0),
        FeedbackRecord(user_id=1, food_id=11, score=1.0),
        FeedbackRecord(user_id=2, food_id=12, score=1.0),
        FeedbackRecord(user_id=2, food_id=13, score=1.0),
        FeedbackRecord(user_id=3, food_id=14, score=1.0),
        FeedbackRecord(user_id=3, food_id=15, score=1.0),
    ]
    model = ExplicitFeedbackCollaborativeFilter(
        minimum_interactions=6,
        minimum_users=3,
        minimum_foods=6,
        minimum_target_user_interactions=2,
    ).fit(records)

    assert model.readiness_for(1).ready is True
    assert model.score_unseen_foods(1) == {}


def test_filter_keeps_last_duplicate_feedback_and_does_not_count_it_twice() -> None:
    records = [
        FeedbackRecord(user_id=1, food_id=10, score=1.0),
        FeedbackRecord(user_id=1, food_id=10, score=-1.0),
        FeedbackRecord(user_id=1, food_id=11, score=1.0),
        FeedbackRecord(user_id=2, food_id=10, score=1.0),
        FeedbackRecord(user_id=2, food_id=12, score=1.0),
    ]
    model = ExplicitFeedbackCollaborativeFilter(
        minimum_interactions=4,
        minimum_users=2,
        minimum_foods=3,
        minimum_target_user_interactions=2,
    ).fit(records)

    readiness = model.readiness_for(1)

    assert readiness.ready is True
    assert readiness.interaction_count == 4
    # The last explicit dislike for food 10 produces no positive neighbor signal.
    assert model.score_unseen_foods(1) == {}


def test_filter_returns_empty_scores_for_a_user_without_explicit_feedback() -> None:
    model = ExplicitFeedbackCollaborativeFilter(
        minimum_interactions=6,
        minimum_users=3,
        minimum_foods=3,
        minimum_target_user_interactions=2,
    ).fit(
        [
            FeedbackRecord(user_id=1, food_id=10, score=1.0),
            FeedbackRecord(user_id=1, food_id=11, score=1.0),
            FeedbackRecord(user_id=2, food_id=10, score=1.0),
            FeedbackRecord(user_id=2, food_id=12, score=1.0),
            FeedbackRecord(user_id=3, food_id=11, score=1.0),
            FeedbackRecord(user_id=3, food_id=12, score=1.0),
        ]
    )

    readiness = model.readiness_for(99)

    assert readiness.ready is False
    assert readiness.reason == "not_enough_target_user_feedback"
    assert model.score_unseen_foods(99) == {}
