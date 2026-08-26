# ============================================================
#  init_database.py — Initialize & Test the Database
#
#  Run this ONCE before starting the API server:
#    python init_database.py
#
#  What it does:
#    1. Checks all required packages are installed
#    2. Applies the versioned Alembic schema migrations
#    3. Inserts a test user and verifies the query works
#    4. Cleans up the test data
# ============================================================

import subprocess
import sys
from pathlib import Path

# ── Make sure we can import the api package ───────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════════════
#  STEP 1 — Check packages
# ════════════════════════════════════════════════════════════
def check_packages():
    required = {
        "fastapi":      "fastapi",
        "uvicorn":      "uvicorn",
        "sqlalchemy":   "sqlalchemy",
        "alembic":      "alembic",
        "jose":         "python-jose[cryptography]",
        "passlib":      "passlib[bcrypt]",
        "pydantic":     "pydantic[email]",
        "multipart":    "python-multipart",
    }
    print("\n[1/5] Checking packages...")
    missing = []
    for module, install_name in required.items():
        try:
            __import__(module)
            print(f"  ✓  {module}")
        except ImportError:
            print(f"  ✗  {module}  ← missing")
            missing.append(install_name)

    if missing:
        print(f"\n  Install missing packages with:")
        print(f"  pip install {' '.join(missing)}")
        print()
        sys.exit(1)


# ════════════════════════════════════════════════════════════
#  STEP 2 — Apply database migrations
# ════════════════════════════════════════════════════════════
def apply_migrations():
    print("\n[2/5] Applying database migrations...")

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        check=True,
    )

    from api.database import engine, DATABASE_URL

    db_file = DATABASE_URL.replace("sqlite:///", "")
    print(f"  ✓  Database : {db_file}")
    print(f"  ✓  Schema   : managed by Alembic")
    print("  ✓  Tables   : users, meal_logs, weekly_plans, foods, food_nutrients, allergens")

    # Show column names for the core runtime tables.
    from sqlalchemy import inspect
    inspector = inspect(engine)
    for table in ["users", "meal_logs", "weekly_plans", "foods", "food_nutrients"]:
        cols = [c["name"] for c in inspector.get_columns(table)]
        print(f"       {table}: {', '.join(cols)}")


# ════════════════════════════════════════════════════════════
#  STEP 3 — Import the curated food catalog
# ════════════════════════════════════════════════════════════
def import_catalog():
    print("\n[3/5] Importing curated food catalog...")
    from api.database import SessionLocal
    from api.services.catalog_import import import_food_catalog

    db = SessionLocal()
    try:
        result = import_food_catalog(db, ROOT / "data" / "foods_clean.csv")
        db.commit()
        print(
            "  ✓  Catalog imported — "
            f"{result['imported_foods']} foods, {result['created_foods']} new rows"
        )
        print("  !  Allergen evidence remains unknown until reviewed catalog evidence is imported")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ════════════════════════════════════════════════════════════
#  STEP 4 — Insert test record and query it back
# ════════════════════════════════════════════════════════════
def test_crud():
    print("\n[4/5] Testing database read/write...")

    from api.database  import SessionLocal
    from api.db_models import User
    from api.auth      import hash_password

    db = SessionLocal()
    try:
        # --- CREATE ---
        test_user = User(
            email           = "test@dietary.local",
            hashed_password = hash_password("test1234"),
            name            = "Test User",
            age             = 25,
            gender          = "male",
            weight          = 75.0,
            height          = 175.0,
            activity_level  = 2,
            goal            = "maintain",
            has_diabetes    = False,
            has_bp          = False,
            has_cholesterol = False,
            allergies       = [],
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"  ✓  INSERT   — user id={test_user.id}, "
              f"email={test_user.email}")

        # --- READ ---
        found = db.query(User).filter(
            User.email == "test@dietary.local"
        ).first()
        assert found is not None
        assert found.name == "Test User"
        print(f"  ✓  SELECT   — found: {found.name}")

        # --- UPDATE ---
        found.weight = 76.5
        db.commit()
        db.refresh(found)
        assert found.weight == 76.5
        print(f"  ✓  UPDATE   — weight → {found.weight}")

        # --- DELETE (cleanup) ---
        db.delete(found)
        db.commit()
        gone = db.query(User).filter(
            User.email == "test@dietary.local"
        ).first()
        assert gone is None
        print(f"  ✓  DELETE   — test record removed")

    except Exception as e:
        db.rollback()
        print(f"  ✗  Database test failed: {e}")
        raise
    finally:
        db.close()


# ════════════════════════════════════════════════════════════
#  STEP 5 — Test JWT auth
# ════════════════════════════════════════════════════════════
def test_auth():
    print("\n[5/5] Testing JWT authentication...")

    from api.auth import hash_password, verify_password, create_token, decode_token

    # Password hashing
    raw      = "MyPassword123"
    hashed   = hash_password(raw)
    assert verify_password(raw, hashed),       "password verify failed"
    assert not verify_password("wrong", hashed),"wrong password should fail"
    print(f"  ✓  Password hashing & verification")

    # Token creation & decoding
    token   = create_token({"sub": "42"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    print(f"  ✓  JWT create & decode")

    # Invalid token
    bad = decode_token("not.a.real.token")
    assert bad is None
    print(f"  ✓  Invalid token correctly rejected")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 52)
    print("  Dietary System — Database Initialization")
    print("=" * 52)

    check_packages()
    apply_migrations()
    import_catalog()
    test_crud()
    test_auth()

    print("\n" + "=" * 52)
    print("  All checks passed!")
    print("  Database is ready.")
    print()
    print("  Start the API server:")
    print("    python run_api.py")
    print()
    print("  Then open:")
    print("    http://127.0.0.1:8000/docs")
    print("=" * 52)