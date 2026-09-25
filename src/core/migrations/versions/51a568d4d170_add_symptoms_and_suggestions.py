"""add_symptoms_and_suggestions

Revision ID: 51a568d4d170
Revises: 346b36a57a28
Create Date: 2026-08-12 19:35:43.511096

"""

from collections.abc import Sequence

revision: str = "51a568d4d170"
down_revision: str | Sequence[str] | None = "346b36a57a28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
