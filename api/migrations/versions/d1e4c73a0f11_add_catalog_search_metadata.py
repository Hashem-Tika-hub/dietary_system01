"""add catalog search metadata

Revision ID: d1e4c73a0f11
Revises: c4b2e8f1d9a0
Create Date: 2026-08-26 17:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e4c73a0f11"
down_revision: Union[str, Sequence[str], None] = "c4b2e8f1d9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("foods") as batch_op:
        batch_op.add_column(
            sa.Column("health_score", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("diabetic_friendly", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("low_sodium", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("is_high_protein", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("foods") as batch_op:
        batch_op.drop_column("is_high_protein")
        batch_op.drop_column("low_sodium")
        batch_op.drop_column("diabetic_friendly")
        batch_op.drop_column("health_score")
