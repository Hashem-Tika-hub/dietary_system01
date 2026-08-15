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

from api.database import init_db
import recommender_engine as rec_engine


# ── Startup / Shutdown ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup:
      1. Creates database tables
      2. Loads ML models into memory (stays loaded for all requests)
    """
    print("=" * 52)
    print("  Dietary Recommendation API — Starting up")
    print("=" * 52)

    print("  [1/2] Initializing database...")
    init_db()

    print("  [2/2] Loading ML models...")
    try:
        rec_engine.get_engine()          # warm up — loads CBF + CF
        print("  ✓ CBF model loaded")
        print("  ✓ CF  model loaded")
    except Exception as e:
        print(f"  ⚠  ML models not found: {e}")
        print("     Run: python run_phase2.py  to train them first")

    print("=" * 52)
    print("  API ready at: http://127.0.0.1:8000")
    print("  Swagger docs:  http://127.0.0.1:8000/docs")
    print("=" * 52)

    yield   # ← server is running

    print("\n  Shutting down...")


# ── Application ───────────────────────────────────────────
app = FastAPI(
    title       = "Dietary Recommendation API",
    description = """
## Smart Personalized Dietary Plan System

An intelligent API that suggests personalized meal plans using Machine Learning.

### Features
- **JWT Authentication** — Secure register / login
- **Hybrid Recommendations** — CBF (60%) + CF (40%)
- **Health Filters** — Diabetes, hypertension, allergies
- **Weekly Meal Plans** — 7-day full plan generation
- **Food Database** — Search 800+ foods with nutritional data

### Flow
1. `POST /auth/register` — Create account
2. `POST /auth/login` — Get JWT token
3. `GET /users/nutrition-targets` — See your daily calorie targets
4. `POST /recommendations/meal` — Get meal recommendations
5. `POST /recommendations/weekly` — Generate a 7-day plan
    """,
    version     = "1.0.0",
    lifespan    = lifespan,
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
        "version": "1.0.0",
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