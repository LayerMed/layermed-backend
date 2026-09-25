"""remove_doctor_from_bookings_and_add_dob_to_users

Revision ID: 489f333f60ad
Revises: c59a37d477df
Create Date: 2026-08-08 17:09:44.205779

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "489f333f60ad"
down_revision: str | Sequence[str] | None = "c59a37d477df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("bookings_doctor_id_fkey", "bookings", type_="foreignkey")
    op.drop_column("bookings", "doctor_id")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS date_of_birth DATE")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS date_of_birth")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS birth_date")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS age")
    op.add_column(
        "bookings",
        sa.Column("doctor_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        "bookings_doctor_id_fkey",
        "bookings",
        "doctors",
        ["doctor_id"],
        ["id"],
        ondelete="CASCADE",
    )