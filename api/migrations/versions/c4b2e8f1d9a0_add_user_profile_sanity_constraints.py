"""Add non-diagnostic sanity constraints to user profiles."""

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


def _batch_recreate_mode() -> str:
    """Rebuild only SQLite tables; PostgreSQL supports direct constraint ALTERs.

    SQLite needs batch recreation to add or remove check constraints. Forcing
    that reconstruction on PostgreSQL would attempt to drop ``users`` while
    dependent foreign keys already exist in runtime tables.
    """

    return "always" if op.get_bind().dialect.name == "sqlite" else "auto"


def upgrade() -> None:
    """Add non-diagnostic sanity checks to the users table."""

    with op.batch_alter_table("users", recreate=_batch_recreate_mode()) as batch_op:
        for name, condition in USER_PROFILE_CHECKS:
            batch_op.create_check_constraint(name, condition)


def downgrade() -> None:
    """Remove the profile sanity checks."""

    with op.batch_alter_table("users", recreate=_batch_recreate_mode()) as batch_op:
        for name, _ in USER_PROFILE_CHECKS:
            batch_op.drop_constraint(name, type_="check")
