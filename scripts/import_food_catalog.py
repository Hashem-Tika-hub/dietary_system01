#!/usr/bin/env python3
"""Import the curated food CSV into the configured catalog database.

The database schema must already be at the Alembic head.  This command is
idempotent for a source code and does not manufacture allergen evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.database import SessionLocal, assert_database_schema_is_current
from api.services.catalog_import import CatalogImportError, import_food_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="استيراد كتالوج الأطعمة إلى قاعدة البيانات")
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "data" / "foods_clean.csv",
        help="مسار CSV المعالج للكتالوج",
    )
    parser.add_argument("--source-code", default="curated-foods-csv")
    parser.add_argument("--source-name", default="Curated foods CSV import")
    args = parser.parse_args()

    assert_database_schema_is_current()
    session = SessionLocal()
    try:
        result = import_food_catalog(
            session,
            args.csv,
            source_code=args.source_code,
            source_name=args.source_name,
        )
        session.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except CatalogImportError as exc:
        session.rollback()
        raise SystemExit(str(exc))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
