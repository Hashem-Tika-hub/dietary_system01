# ============================================================
#  api/database.py — إعداد الاتصال بقاعدة البيانات
# ============================================================
#
# لا يُنشئ هذا الملف الجداول ولا يغيّر المخطط تلقائيًا. تُدار كل
# تغييرات المخطط حصريًا عبر Alembic:
#
#     alembic upgrade head
#
# SQLite للتطوير المحلي والاختبارات ونسخة الكتالوج المرجعية فقط.
# PostgreSQL هو محرك قاعدة البيانات التشغيلي في الإنتاج.
# ============================================================

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ── رابط قاعدة البيانات ───────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "data" / "dietary.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
SUPPORTED_DATABASE_BACKENDS = frozenset({"sqlite", "postgresql"})


def get_database_backend(database_url: str) -> str:
    """Return the supported SQLAlchemy backend without exposing credentials."""

    try:
        backend = make_url(database_url).get_backend_name()
    except ArgumentError as error:
        raise RuntimeError("DATABASE_URL غير صالح. استخدم رابط SQLAlchemy صالحًا.") from error

    if backend not in SUPPORTED_DATABASE_BACKENDS:
        supported = ", ".join(sorted(SUPPORTED_DATABASE_BACKENDS))
        raise RuntimeError(
            "محرك قاعدة البيانات غير مدعوم. "
            f"المحركات المدعومة: {supported}."
        )
    return backend


DATABASE_BACKEND = get_database_backend(DATABASE_URL)

# SQLite يحتاج هذا الخيار عند استخدام جلسات من عدة threads في FastAPI.
# PostgreSQL يتعامل مع التزامن عبر MVCC؛ pool_pre_ping يتجنب تسليم اتصال
# منقطع بعد إعادة تشغيل القاعدة أو الشبكة إلى طلب API جديد.
engine_options: dict[str, object] = {"echo": False}
if DATABASE_BACKEND == "sqlite":
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class المشتركة لنماذج SQLAlchemy."""


class DatabaseMigrationRequiredError(RuntimeError):
    """Raised when the configured database has not been prepared by Alembic."""


REQUIRED_TABLES = frozenset({
    "users",
    "meal_logs",
    "weekly_plans",
    "catalog_sources",
    "foods",
    "food_nutrients",
    "allergens",
    "food_allergens",
    "ingredient_allergens",
})


def assert_database_schema_is_current() -> None:
    """Verify that Alembic, not application startup, created the schema.

    This is intentionally a readiness check rather than a migration mechanism.
    A missing or unmanaged schema causes a clear startup error with the exact
    command the operator must run instead of silently applying DDL at runtime.
    """

    table_names = set(inspect(engine).get_table_names())
    missing_tables = REQUIRED_TABLES - table_names

    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise DatabaseMigrationRequiredError(
            "قاعدة البيانات غير جاهزة. الجداول المفقودة: "
            f"{missing}. نفّذ: alembic upgrade head"
        )

    if "alembic_version" not in table_names:
        raise DatabaseMigrationRequiredError(
            "قاعدة البيانات موجودة لكنها غير مُدارة بواسطة Alembic. "
            "للبيئات القائمة راجع دليل الترحيل ثم نفّذ alembic stamp head؛ "
            "وللقواعد الجديدة نفّذ alembic upgrade head."
        )


def get_db():
    """FastAPI dependency — يفتح جلسة DB ويغلقها تلقائيًا."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
