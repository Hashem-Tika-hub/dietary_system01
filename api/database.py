# ============================================================
#  api/database.py — إعداد الاتصال بقاعدة البيانات
# ============================================================
#
# لا يُنشئ هذا الملف الجداول ولا يغيّر المخطط تلقائيًا. تُدار كل
# تغييرات المخطط حصريًا عبر Alembic:
#
#     alembic upgrade head
#
# هذا يمنع اختلاف المخطط بين بيئات التطوير والاختبار والنشر، ويجعل
# كل تعديل قابلًا للمراجعة والرجوع.
# ============================================================

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ── رابط قاعدة البيانات ───────────────────────────────────
# SQLite للتطوير المحلي. في الإنتاج استخدم DATABASE_URL لخدمة
# PostgreSQL أو قاعدة البيانات المدارة المناسبة.
DB_PATH = Path(__file__).parent.parent / "data" / "dietary.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# SQLite يحتاج هذا الخيار عند استخدام جلسات من عدة threads في FastAPI.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class المشتركة لنماذج SQLAlchemy."""


class DatabaseMigrationRequiredError(RuntimeError):
    """Raised when the configured database has not been prepared by Alembic."""


REQUIRED_TABLES = frozenset({"users", "meal_logs", "weekly_plans"})


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
