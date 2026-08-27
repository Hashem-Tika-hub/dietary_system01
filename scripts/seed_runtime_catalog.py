"""Seed the mutable runtime database from the reviewed catalog snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.database import SessionLocal, assert_database_schema_is_current
from api.services.reference_catalog_seed import seed_reference_catalog
from config import REFERENCE_FOOD_CATALOG_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy the catalog-only reference snapshot into DATABASE_URL."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=REFERENCE_FOOD_CATALOG_PATH,
        help="Catalog-only SQLite snapshot to load (default: repository reference snapshot).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assert_database_schema_is_current()
    db = SessionLocal()
    try:
        result = seed_reference_catalog(db, args.snapshot)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "Runtime catalog synchronized: "
        f"{result['catalog_sources']} sources, {result['foods']} foods, "
        f"{result['food_nutrients']} nutrients, {result['food_portions']} portions."
    )


if __name__ == "__main__":
    main()
