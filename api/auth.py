# ============================================================
#  api/auth.py — JWT Authentication
#  Uses bcrypt directly (avoids passlib compatibility issues)
# ============================================================

import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

# ── Secret key — change this in production! ───────────────
SECRET_KEY        = os.getenv("SECRET_KEY",
                               "dietary-system-secret-key-2026-change-me")
ALGORITHM         = "HS256"
TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    salt   = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compare plain password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            hashed.encode("utf-8")
        )
    except Exception:
        return False


def create_token(data: dict,
                 expires_delta: Optional[timedelta] = None) -> str:
    """إنشاء JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(days=TOKEN_EXPIRE_DAYS)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """فكّ تشفير الـ Token واسترجاع البيانات"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None