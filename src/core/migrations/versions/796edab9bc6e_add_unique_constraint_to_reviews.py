"""add_unique_constraint_to_reviews

Revision ID: 796edab9bc6e
Revises: ffa26646d733
Create Date: 2026-08-29 17:46:57.637373

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "796edab9bc6e"
down_revision: str | Sequence[str] | None = "ffa26646d733"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass