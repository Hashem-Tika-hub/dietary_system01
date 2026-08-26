"""Catalog-backed allergy eligibility for recommendation candidates.

This service is intentionally independent from scoring.  It evaluates only
catalog evidence and returns audit-friendly decisions before CBF, CF, or
diversity logic sees a candidate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from api.db_models import Allergen, Food, FoodAllergen, FoodIngredient, IngredientAllergen
from meal_rules import declared_allergen_codes


BLOCKED = "blocked"
ELIGIBLE = "eligible"
UNKNOWN_METADATA = "unknown_metadata"


@dataclass(frozen=True)
class AllergyEligibilityDecision:
    """A catalog-evidence decision for one external food identifier."""

    external_id: str
    status: str
    blocked_codes: tuple[str, ...] = ()
    unknown_codes: tuple[str, ...] = ()

    @property
    def is_eligible(self) -> bool:
        return self.status == ELIGIBLE


def _statuses_by_food_and_code(rows) -> dict[str, dict[str, set[str]]]:
    result: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for external_id, allergen_code, status in rows:
        result[str(external_id)][str(allergen_code)].add(str(status))
    return result


def _code_status(
    food_statuses: set[str],
    ingredient_statuses: set[str],
) -> str:
    """Resolve one declared allergen with conservative, evidence-aware precedence.

    ``present`` in either evidence layer always blocks.  An explicit final
    food-level ``absent`` record is sufficient after that check.  Ingredient
    evidence is used when a final food-level record is absent.  Missing or
    unknown evidence remains unknown rather than being treated as safe.
    """
    combined = food_statuses | ingredient_statuses
    if "present" in combined:
        return BLOCKED
    if "absent" in food_statuses:
        return ELIGIBLE
    if "unknown" in food_statuses:
        return UNKNOWN_METADATA
    if "absent" in ingredient_statuses:
        return ELIGIBLE
    return UNKNOWN_METADATA


def evaluate_catalog_allergy_eligibility(
    db: Session,
    external_ids: Iterable[str],
    declared_allergies: Iterable[str],
) -> dict[str, AllergyEligibilityDecision]:
    """Evaluate catalog allergy evidence for every requested candidate.

    With no declared allergies, every supplied ID is eligible and no catalog
    lookup is needed.  With declared allergies, each code must have explicit
    non-conflicting evidence.  Candidates with missing or unknown evidence are
    returned as ``unknown_metadata`` so callers can apply a conservative policy
    before ranking.
    """
    candidate_ids = {str(value) for value in external_ids if value is not None}
    declared_codes = declared_allergen_codes(list(declared_allergies or []))
    if not declared_codes:
        return {
            external_id: AllergyEligibilityDecision(external_id, ELIGIBLE)
            for external_id in candidate_ids
        }

    if not candidate_ids:
        return {}

    food_rows = (
        db.query(Food.external_id, Allergen.code, FoodAllergen.status)
        .join(FoodAllergen, FoodAllergen.food_id == Food.id)
        .join(Allergen, Allergen.id == FoodAllergen.allergen_id)
        .filter(
            Food.is_active.is_(True),
            Food.external_id.in_(candidate_ids),
            Allergen.code.in_(declared_codes),
        )
        .all()
    )
    ingredient_rows = (
        db.query(Food.external_id, Allergen.code, IngredientAllergen.status)
        .join(FoodIngredient, FoodIngredient.food_id == Food.id)
        .join(IngredientAllergen, IngredientAllergen.ingredient_id == FoodIngredient.ingredient_id)
        .join(Allergen, Allergen.id == IngredientAllergen.allergen_id)
        .filter(
            Food.is_active.is_(True),
            Food.external_id.in_(candidate_ids),
            Allergen.code.in_(declared_codes),
        )
        .all()
    )
    food_evidence = _statuses_by_food_and_code(food_rows)
    ingredient_evidence = _statuses_by_food_and_code(ingredient_rows)

    decisions: dict[str, AllergyEligibilityDecision] = {}
    for external_id in candidate_ids:
        blocked_codes: list[str] = []
        unknown_codes: list[str] = []
        for code in sorted(declared_codes):
            resolved = _code_status(
                food_evidence.get(external_id, {}).get(code, set()),
                ingredient_evidence.get(external_id, {}).get(code, set()),
            )
            if resolved == BLOCKED:
                blocked_codes.append(code)
            elif resolved == UNKNOWN_METADATA:
                unknown_codes.append(code)

        status = (
            BLOCKED
            if blocked_codes
            else UNKNOWN_METADATA
            if unknown_codes
            else ELIGIBLE
        )
        decisions[external_id] = AllergyEligibilityDecision(
            external_id=external_id,
            status=status,
            blocked_codes=tuple(blocked_codes),
            unknown_codes=tuple(unknown_codes),
        )
    return decisions


def eligible_external_ids(
    db: Session,
    external_ids: Iterable[str],
    declared_allergies: Iterable[str],
) -> set[str]:
    """Return only candidates with explicit non-conflicting catalog evidence."""
    return {
        external_id
        for external_id, decision in evaluate_catalog_allergy_eligibility(
            db, external_ids, declared_allergies
        ).items()
        if decision.is_eligible
    }
