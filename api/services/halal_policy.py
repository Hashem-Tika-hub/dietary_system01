"""Conservative cultural food-eligibility helpers.

This module excludes a food only when a trusted catalog description contains an
explicit pork or alcoholic-beverage indicator.  An allowed result means only
that no configured indicator was found; it is **not** a halal certification and
does not establish ingredient provenance, slaughter method, cross-contact, or
local regulatory compliance.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd


# The list intentionally favors precision over broad guessing.  Terms such as
# gelatin, flavoring, stock, or Arabic substrings are not enough to establish a
# prohibited ingredient without reviewed ingredient evidence.
_EXPLICIT_PORK_PATTERN = re.compile(
    r"(?:\b(?:pork|pig|ham|bacon|prosciutto|lard|salami|pepperoni|chorizo)\b|خنزير)",
    re.IGNORECASE,
)
_EXPLICIT_ALCOHOL_PATTERN = re.compile(
    r"(?:\b(?:alcohol|ethanol|beer|wine|whisk(?:e)?y|vodka|rum|brandy|"
    r"liqueur|cider|sake|sherry|vermouth|bourbon|gin|tequila|mead|ale|"
    r"lager|porter|stout)\b|كحول|نبيذ|بيرة|خمر|ويسكي|فودكا)",
    re.IGNORECASE,
)
_ALCOHOL_FREE_PATTERN = re.compile(
    r"(?:\b(?:alcohol[- ]free|non[- ]alcoholic|de[- ]alcoholized)\b|"
    r"(?:خالي|خالٍ)\s+من\s+الكحول|بدون\s+كحول)",
    re.IGNORECASE,
)

PORK_REASON = "explicit_pork_indicator"
ALCOHOL_REASON = "explicit_alcohol_indicator"


def explicit_non_halal_reasons(*text_values: object) -> tuple[str, ...]:
    """Return configured explicit restriction indicators found in text fields.

    This function does not infer ingredients from food categories and does not
    use a missing match as proof that the food is halal.
    """
    normalized = " ".join(
        str(value).strip()
        for value in text_values
        if value is not None and str(value).strip()
    )
    reasons: list[str] = []
    if _EXPLICIT_PORK_PATTERN.search(normalized):
        reasons.append(PORK_REASON)
    if (
        _EXPLICIT_ALCOHOL_PATTERN.search(normalized)
        and not _ALCOHOL_FREE_PATTERN.search(normalized)
    ):
        reasons.append(ALCOHOL_REASON)
    return tuple(reasons)


def is_explicitly_non_halal(*text_values: object) -> bool:
    """Return whether trusted description text has an explicit restriction."""
    return bool(explicit_non_halal_reasons(*text_values))


def apply_cultural_food_exclusions(
    foods: pd.DataFrame,
    *,
    text_columns: Iterable[str] = ("name", "description"),
) -> pd.DataFrame:
    """Remove explicit pork/alcohol matches before recommendation ranking.

    Missing text is retained because absence of a keyword cannot prove either
    eligibility or ineligibility.  Catalog-backed allergen evidence remains a
    separate, stricter decision path for users who declare an allergy.
    """
    out = foods.copy()
    available_columns = [column for column in text_columns if column in out.columns]
    if not available_columns:
        return out
    blocked = out[available_columns].apply(
        lambda row: is_explicitly_non_halal(*row.tolist()), axis=1
    )
    return out.loc[~blocked].copy()
