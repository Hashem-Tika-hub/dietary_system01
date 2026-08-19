"""Collaborative filtering based only on explicit, consented food feedback.

This module intentionally never consumes meal logs or synthetic ratings. It
builds a user-item matrix from explicit feedback records and provides scores
only when dataset coverage is sufficient. It is a scoring component; hard food
safety filters must still run before any resulting score is exposed as a meal
recommendation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class FeedbackRecord:
    """Minimal, storage-independent explicit feedback record."""

    user_id: int
    food_id: int
    score: float


@dataclass(frozen=True)
class CollaborativeReadiness:
    """Dataset coverage required before collaborative scores are usable."""

    ready: bool
    reason: str
    interaction_count: int
    unique_users: int
    unique_foods: int
    target_user_interactions: int


class ExplicitFeedbackCollaborativeFilter:
    """User-based CF over explicit food feedback with conservative gating."""

    def __init__(
        self,
        *,
        minimum_interactions: int = 10,
        minimum_users: int = 3,
        minimum_foods: int = 3,
        minimum_target_user_interactions: int = 2,
    ) -> None:
        if min(
            minimum_interactions,
            minimum_users,
            minimum_foods,
            minimum_target_user_interactions,
        ) < 1:
            raise ValueError("Minimum collaborative-filtering thresholds must be positive")
        self.minimum_interactions = minimum_interactions
        self.minimum_users = minimum_users
        self.minimum_foods = minimum_foods
        self.minimum_target_user_interactions = minimum_target_user_interactions
        self._user_ids: list[int] = []
        self._food_ids: list[int] = []
        self._matrix = np.empty((0, 0), dtype=float)
        self._feedback_counts: Counter[int] = Counter()
        self._interaction_count = 0

    def fit(self, records: Iterable[FeedbackRecord]) -> "ExplicitFeedbackCollaborativeFilter":
        """Fit the matrix from current explicit feedback records.

        A database uniqueness rule keeps one latest feedback value per
        ``(user_id, food_id)`` pair. The method defensively handles duplicate
        input by retaining the last record received for each pair.
        """

        latest: dict[tuple[int, int], float] = {}
        for record in records:
            if record.score not in {-1.0, 0.5, 1.0}:
                raise ValueError("Feedback scores must be -1.0, 0.5, or 1.0")
            latest[(record.user_id, record.food_id)] = record.score

        self._interaction_count = len(latest)
        self._user_ids = sorted({user_id for user_id, _ in latest})
        self._food_ids = sorted({food_id for _, food_id in latest})
        self._feedback_counts = Counter(user_id for user_id, _ in latest)

        self._matrix = np.zeros((len(self._user_ids), len(self._food_ids)), dtype=float)
        user_index = {user_id: index for index, user_id in enumerate(self._user_ids)}
        food_index = {food_id: index for index, food_id in enumerate(self._food_ids)}
        for (user_id, food_id), score in latest.items():
            self._matrix[user_index[user_id], food_index[food_id]] = score
        return self

    def readiness_for(self, user_id: int) -> CollaborativeReadiness:
        """Explain whether the model can safely score unseen foods for a user."""

        target_count = self._feedback_counts.get(user_id, 0)
        if self._interaction_count < self.minimum_interactions:
            reason = "not_enough_explicit_feedback"
        elif len(self._user_ids) < self.minimum_users:
            reason = "not_enough_distinct_users"
        elif len(self._food_ids) < self.minimum_foods:
            reason = "not_enough_distinct_foods"
        elif target_count < self.minimum_target_user_interactions:
            reason = "not_enough_target_user_feedback"
        else:
            return CollaborativeReadiness(
                ready=True,
                reason="ready",
                interaction_count=self._interaction_count,
                unique_users=len(self._user_ids),
                unique_foods=len(self._food_ids),
                target_user_interactions=target_count,
            )

        return CollaborativeReadiness(
            ready=False,
            reason=reason,
            interaction_count=self._interaction_count,
            unique_users=len(self._user_ids),
            unique_foods=len(self._food_ids),
            target_user_interactions=target_count,
        )

    def score_unseen_foods(self, user_id: int) -> dict[int, float]:
        """Return normalized scores for unseen food IDs when readiness passes."""

        readiness = self.readiness_for(user_id)
        if not readiness.ready:
            return {}

        user_index = self._user_ids.index(user_id)
        target_vector = self._matrix[user_index : user_index + 1]
        similarities = cosine_similarity(target_vector, self._matrix)[0]
        similarities[user_index] = 0.0
        positive_similarities = np.clip(similarities, 0.0, None)
        denominator = positive_similarities.sum()
        if denominator == 0:
            return {}

        raw_scores = positive_similarities @ self._matrix / denominator
        unseen = self._matrix[user_index] == 0
        scores = {
            food_id: float(raw_scores[index])
            for index, food_id in enumerate(self._food_ids)
            if unseen[index] and raw_scores[index] > 0
        }
        if not scores:
            return {}

        minimum = min(scores.values())
        maximum = max(scores.values())
        if maximum == minimum:
            return {food_id: 1.0 for food_id in scores}
        return {
            food_id: (score - minimum) / (maximum - minimum)
            for food_id, score in scores.items()
        }
