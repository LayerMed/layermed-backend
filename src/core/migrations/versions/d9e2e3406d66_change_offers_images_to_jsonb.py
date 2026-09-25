"""change offers images to jsonb

Revision ID: d9e2e3406d66
Revises: 09fac1b6484b
Create Date: 2026-09-07 14:09:20.709416

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d9e2e3406d66"
down_revision: Union[str, Sequence[str], None] = "09fac1b6484b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "offers",
        "images",
        existing_type=postgresql.ARRAY(sa.VARCHAR()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="to_jsonb(images)",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION pg_temp.jsonb_to_varchar_array(j jsonb) 
        RETURNS varchar[] LANGUAGE sql IMMUTABLE AS 
        $$ SELECT ARRAY(SELECT jsonb_array_elements_text(j)) $$;
        """
    )
    op.execute(
        """
        ALTER TABLE offers 
        ALTER COLUMN images TYPE varchar[] 
        USING pg_temp.jsonb_to_varchar_array(images);
        """
    )