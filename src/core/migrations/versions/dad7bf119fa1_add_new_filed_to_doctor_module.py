"""add_new_filed_to_doctor_module

Revision ID: dad7bf119fa1
Revises: b07869fc99bd
Create Date: 2026-08-27 16:32:44.953197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dad7bf119fa1'
down_revision: Union[str, Sequence[str], None] = 'b07869fc99bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bookingstatus_enum = postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookingstatus')
    bookingstatus_enum.create(op.get_bind(), checkfirst=True)

    op.alter_column('bookings', 'status',
               existing_type=postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookstatus'),
               type_=sa.Enum('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookingstatus'),
               existing_nullable=False,
               postgresql_using='status::text::bookingstatus')
               
    op.add_column('doctors', sa.Column('degree', sa.String(), nullable=True))
    op.add_column('doctors', sa.Column('min_price', sa.Integer(), nullable=False))
    op.add_column('doctors', sa.Column('clinic', sa.String(), nullable=False))
    op.add_column('doctors', sa.Column('avatar_url', sa.String(), nullable=True))
    op.add_column('doctors', sa.Column('rating_avg', sa.Float(), nullable=False))
    op.add_column('doctors', sa.Column('reviews_count', sa.Integer(), nullable=False))
    
    bookstatus_enum = postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookstatus')
    bookstatus_enum.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bookstatus_enum = postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookstatus')
    bookstatus_enum.create(op.get_bind(), checkfirst=True)

    op.drop_column('doctors', 'reviews_count')
    op.drop_column('doctors', 'rating_avg')
    op.drop_column('doctors', 'avatar_url')
    op.drop_column('doctors', 'clinic')
    op.drop_column('doctors', 'min_price')
    op.drop_column('doctors', 'degree')
    
    op.alter_column('bookings', 'status',
               existing_type=sa.Enum('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookingstatus'),
               type_=postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookstatus'),
               existing_nullable=False,
               postgresql_using='status::text::bookstatus')
               
    bookingstatus_enum = postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='bookingstatus')
    bookingstatus_enum.drop(op.get_bind(), checkfirst=True)

