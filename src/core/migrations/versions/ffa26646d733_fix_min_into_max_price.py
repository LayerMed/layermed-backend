"""fix_min_into_max_price

Revision ID: ffa26646d733
Revises: c994027af9a7
Create Date: 2026-08-27 18:27:07.975546

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ffa26646d733"
down_revision: str | Sequence[str] | None = "c994027af9a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    doctorstatus_enum = postgresql.ENUM(
        "APPROVED", "PENDING", "REJECTED", name="doctorstatus"
    )
    doctorstatus_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "doctors",
        sa.Column(
            "status",
            doctorstatus_enum,
            server_default="PENDING",
            nullable=False,
        ),
    )
    op.add_column("doctors", sa.Column("rejection_reason", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("doctors", "rejection_reason")
    op.drop_column("doctors", "status")
    doctorstatus_enum = postgresql.ENUM(
        "APPROVED", "PENDING", "REJECTED", name="doctorstatus"
    )
    doctorstatus_enum.drop(op.get_bind(), checkfirst=True)
