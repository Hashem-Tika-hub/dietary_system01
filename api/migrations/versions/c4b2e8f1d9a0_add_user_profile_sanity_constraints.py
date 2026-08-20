"""add user profile sanity constraints

Revision ID: c4b2e8f1d9a0
Revises: a298050d9bcf
Create Date: 2026-08-20 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
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


def upgrade() -> None:
    """Add non-diagnostic sanity checks to the users table.

    Batch mode recreates the table on SQLite, while remaining compatible with
    PostgreSQL deployments. Existing production data must satisfy these checks
    before the migration is applied.
    """
    with op.batch_alter_table("users", recreate="always") as batch_op:
        for name, condition in USER_PROFILE_CHECKS:
            batch_op.create_check_constraint(name, condition)


def downgrade() -> None:
    """Remove the profile sanity checks."""
    with op.batch_alter_table("users", recreate="always") as batch_op:
        for name, _ in USER_PROFILE_CHECKS:
            batch_op.drop_constraint(name, type_="check")
