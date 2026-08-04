# ============================================================
#  api/database.py — إعداد قاعدة البيانات
#  يستخدم SQLite للتطوير المحلي (لا يحتاج تثبيت)
#  غيّر DATABASE_URL لـ PostgreSQL في الإنتاج
# ============================================================

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path

# ── رابط قاعدة البيانات ───────────────────────────────────
# SQLite للتطوير المحلي (لا يحتاج تثبيت)
DB_PATH      = Path(__file__).parent.parent / "data" / "dietary.db"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)

# للإنتاج مع PostgreSQL:
# DATABASE_URL = "postgresql://user:password@localhost:5432/dietary_db"

# ── إنشاء المحرك ──────────────────────────────────────────
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,     # True لرؤية SQL في الـ terminal
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — يفتح جلسة DB ويغلقها تلقائياً"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _auto_migrate(engine):
    """
    إصلاح تلقائي خفيف لقاعدة بيانات قديمة أُنشئت قبل إضافة أعمدة جديدة
    لموديل User (مثل dislikes/favorites/cuisine_style/allow_treats).
    create_all() لا يُعدّل جداول موجودة أصلاً — فقاعدة بيانات من نسخة
    سابقة تبقى بدون الأعمدة الجديدة وتفشل كل طلب بخطأ SQL غامض
    ("no such column"). هذا يكتشف الأعمدة الناقصة ويضيفها مباشرة
    (SQLite تدعم ALTER TABLE ADD COLUMN). لا يحذف أو يُعدّل شيئًا موجودًا.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return  # جدول جديد كليًا — create_all تكفّل بإنشائه بكل أعمدته

    existing = {c["name"] for c in inspector.get_columns("users")}
    expected = {
        "dislikes":      ("JSON",        "'[]'"),
        "favorites":     ("JSON",        "'[]'"),
        "cuisine_style": ("VARCHAR(20)", "'مزيج'"),
        "allow_treats":  ("BOOLEAN",     "0"),
    }
    missing = {k: v for k, v in expected.items() if k not in existing}
    if not missing:
        return

    print(f"  [!] قاعدة بيانات من نسخة سابقة — أعمدة ناقصة: {list(missing)}")
    print(f"      يجري إصلاحها تلقائيًا (لن تُفقَد أي بيانات موجودة)...")
    with engine.connect() as conn:
        for col, (sql_type, default) in missing.items():
            conn.execute(text(
                f"ALTER TABLE users ADD COLUMN {col} {sql_type} DEFAULT {default}"
            ))
        conn.commit()
    print(f"  ✓ تم إصلاح قاعدة البيانات")


def init_db():
    """إنشاء الجداول عند أول تشغيل"""
    from api.db_models import User, MealLog, WeeklyPlan   # noqa
    Base.metadata.create_all(bind=engine)
    _auto_migrate(engine)
    print(f"  ✓ قاعدة البيانات: {DATABASE_URL}")