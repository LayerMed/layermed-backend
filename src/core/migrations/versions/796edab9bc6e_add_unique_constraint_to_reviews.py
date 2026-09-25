"""add_unique_constraint_to_reviews

Revision ID: 796edab9bc6e
Revises: ffa26646d733
Create Date: 2026-08-29 17:46:57.637373

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "796edab9bc6e"
down_revision: Union[str, Sequence[str], None] = "ffa26646d733"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass