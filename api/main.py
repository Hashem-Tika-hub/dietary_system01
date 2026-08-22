# ============================================================
#  api/main.py — FastAPI Application Entry Point
#  Start server: python run_api.py
#  Docs:         http://127.0.0.1:8000/docs
# ============================================================

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from api.limiter import limiter

# Add project root to Python path so we can import ML modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import assert_database_schema_is_current
import recommender_engine as rec_engine


# ── Startup / Shutdown ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup:
      1. Verifies that Alembic prepared the database schema
      2. Loads the content model and prepares explicit-feedback ranking
    """
    print("=" * 52)
    print("  Dietary Recommendation API — Starting up")
    print("=" * 52)

    print("  [1/2] Verifying database migrations...")
    assert_database_schema_is_current()
    print("  ✓ Database schema is managed by Alembic")

    print("  [2/2] Loading recommendation models...")
    try:
        rec_engine.get_engine()          # warm up — loads content model
        print("  ✓ CBF model loaded")
        print("  ✓ Explicit-feedback CF activates after readiness checks")
    except Exception as e:
        print(f"  ⚠  ML models not found: {e}")
        print("     Run: python run_phase2.py  to train them first")

    print("=" * 52)
    print("  API ready at: http://127.0.0.1:8000")
    print("  Swagger docs:  http://127.0.0.1:8000/docs")
    print("=" * 52)

    yield   # ← server is running

    print("\n  Shutting down...")


# ── Application / OpenAPI ─────────────────────────────────
OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "فحص جاهزية الخدمة وقاعدة البيانات والنماذج.",
    },
    {
        "name": "المصادقة",
        "description": "إنشاء حساب وتسجيل الدخول والحصول على JWT.",
    },
    {
        "name": "المستخدم",
        "description": "إدارة الملف الشخصي والأهداف الغذائية وسجل الوجبات.",
    },
    {
        "name": "Recommendations",
        "description": "اقتراح الوجبات والخطط الأسبوعية والبدائل. القيود الصلبة تطبق قبل الترتيب.",
    },
    {
        "name": "Foods",
        "description": "البحث عن الأطعمة وعرض بياناتها الغذائية.",
    },
]

app = FastAPI(
    title="Dietary Recommendation API",
    description="""
## نظام توصية وجبات وخطط غذائية شخصية

تساعد هذه الواجهة تطبيقات الويب والموبايل على إدارة ملفات المستخدمين،
سجل الوجبات، وخطط الوجبات المقترحة.

> **حدود السلامة:** القيود الصلبة، مثل الحساسية وملاءمة الوجبة، تطبق قبل
> ترتيب المرشحات. يعتمد الترتيب حاليًا على المحتوى افتراضيًا؛ لا يُفعل
> الترتيب التعاوني إلا بعد توافر تفاعلات صريحة وحقيقية من المستخدمين.

### بدء سريع
1. استخدم `POST /auth/register` لإنشاء حساب، ثم `POST /auth/login` للحصول على JWT.
2. اضغط **Authorize** داخل Swagger وأدخل `Bearer <access_token>`.
3. حدّث الملف عبر `PUT /users/profile` وأضف تفضيلات وقيود الطعام.
4. استخدم `POST /recommendations/meal` أو `POST /recommendations/weekly`.

### التوثيق
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- مخطط OpenAPI: `/openapi.json`
    """,
    version="1.1.0",
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Dietary System Project"},
    license_info={"name": "Academic project"},
    lifespan=lifespan,
)


# ── Rate limiting — حماية /auth/login و/auth/register من brute force ──
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS — allow Flutter app to connect ──────────────────
# طلبات تطبيق الموبايل (native) ما تتأثر بـ CORS أصلاً — هذا يخص فقط
# الوصول من متصفح (Swagger UI، أو نسخة Flutter web). القيمة الافتراضية
# محصورة بـ localhost للتطوير؛ حدّد ALLOWED_ORIGINS كمتغير بيئة
# (دومينات مفصولة بفاصلة) بمجرد نشر التطبيق فعليًا.
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost,http://localhost:3000,http://127.0.0.1"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins  = _allowed_origins,
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# ── Register Routes ───────────────────────────────────────
from api.routes.auth            import router as auth_router
from api.routes.users           import router as users_router
from api.routes.recommendations import router as rec_router
from api.routes.foods           import router as foods_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rec_router)
app.include_router(foods_router)


# ── Health Check ─────────────────────────────────────────
@app.get("/", tags=["Health"], summary="API status")
def root():
    return {
        "status":  "running",
        "name":    "Dietary Recommendation API",
        "version": "1.1.0",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"], summary="Detailed health check")
def health():
    """Check if the API and ML models are ready."""
    try:
        engine = rec_engine.get_engine()
        ml_ok  = engine.is_ready
    except Exception:
        ml_ok  = False

    return {
        "api":        "ok",
        "ml_models":  "ok" if ml_ok else "not loaded",
        "database":   "ok",
    }