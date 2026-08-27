"""Import USDA FoodData Central Foundation Foods into the configured catalog.

By default, the command downloads the official Foundation Foods CSV archive to
an explicit temporary path, imports a deterministic staged batch, then leaves
that archive outside the repository.  It creates no allergen evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.database import SessionLocal, assert_database_schema_is_current
from api.services.catalog_import import CatalogImportError
from api.services.usda_foundation_import import (
    USDA_FOUNDATION_CSV_URL,
    download_usda_foundation_archive,
    import_usda_foundation_catalog,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="استيراد أطعمة USDA Foundation Foods إلى كتالوج الطعام"
    )
    parser.add_argument(
        "--archive",
        type=Path,
        help="مسار أرشيف USDA CSV ZIP محمّل مسبقًا",
    )
    parser.add_argument(
        "--download-to",
        type=Path,
        help="نزّل الأرشيف الرسمي إلى هذا المسار قبل الاستيراد",
    )
    parser.add_argument(
        "--url",
        default=USDA_FOUNDATION_CSV_URL,
        help="رابط أرشيف USDA الرسمي (للاختبار أو عند تغير الإصدار)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=250,
        help="عدد أطعمة Foundation المكتملة في الدفعة؛ استخدم 0 للاستيراد الكامل",
    )
    args = parser.parse_args()

    if args.archive and args.download_to:
        parser.error("استخدم --archive أو --download-to فقط، وليس كليهما")
    if not args.archive and not args.download_to:
        parser.error("حدد --archive أو --download-to")
    if args.limit < 0:
        parser.error("--limit يجب أن يكون صفرًا أو عددًا موجبًا")

    archive = args.archive
    if args.download_to:
        try:
            archive = download_usda_foundation_archive(args.download_to, url=args.url)
        except Exception as exc:
            raise SystemExit(f"تعذر تنزيل أرشيف USDA: {exc}") from exc
    assert archive is not None

    assert_database_schema_is_current()
    session = SessionLocal()
    try:
        result = import_usda_foundation_catalog(
            session,
            archive,
            limit=args.limit or None,
        )
        session.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except CatalogImportError as exc:
        session.rollback()
        raise SystemExit(str(exc)) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
