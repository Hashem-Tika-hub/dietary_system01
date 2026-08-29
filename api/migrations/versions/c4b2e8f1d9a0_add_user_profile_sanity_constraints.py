"""Add user profile sanity constraints.

Revision ID: c4b2e8f1d9a0
Revises: a298050d9bcf
Create Date: 2026-08-20 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4b2e8f1d9a0"
down_revision: Union[str, Sequence[str], None] = "a298050d9bcf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USER_PROFILE_CHECKS = (
    ("ck_users_age_range", "age BETWEEN 10 AND 100"),
    ("ck_users_weight_range", "weight BETWEEN 30.0 AND 300.0"),
    ("ck_users_height_range", "height BETWEEN 100.0 AND 250.0"),
    ("ck_users_activity_level_range", "activity_level BETWEEN 1 AND 5"),
    (
        "ck_users_body_profile_bmi_sanity",
        "weight * 10000.0 / (height * height) BETWEEN 10.0 AND 80.0",
    ),
)


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    """Add non-diagnostic sanity checks without dropping dependent FKs.

    SQLite requires batch table recreation for check constraints. PostgreSQL
    supports adding the constraints directly, so its users primary key and
    dependent foreign keys remain intact.
    """
    if _is_sqlite():
        with op.batch_alter_table("users", recreate="always") as batch_op:
            for name, condition in USER_PROFILE_CHECKS:
                batch_op.create_check_constraint(name, condition)
    else:
        for name, condition in USER_PROFILE_CHECKS:
            op.create_check_constraint(name, "users", condition)


def downgrade() -> None:
    """Remove the profile sanity checks."""
    if _is_sqlite():
        with op.batch_alter_table("users", recreate="always") as batch_op:
            for name, _ in USER_PROFILE_CHECKS:
                batch_op.drop_constraint(name, type_="check")
    else:
        for name, _ in reversed(USER_PROFILE_CHECKS):
            op.drop_constraint(name, "users", type_="check")
