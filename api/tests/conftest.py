"""Shared pytest setup for API tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Authentication validates this variable during module import. The fixed value
# is test-only and never used by production configuration.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
