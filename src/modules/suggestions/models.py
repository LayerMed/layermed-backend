from sqlalchemy import Index
from sqlalchemy.orm import Mapped
from src.core.database import Base, Timestamp


class Suggest(Base, Timestamp):
    __tablename__ = 'suggestions'

    doctor_id: Mapped[int]
    title: Mapped[str]
    description: Mapped[str]
    cost: Mapped[int]
    suggest_format: Mapped[str]
    duration: Mapped[int]

    __table_args__ = (
        Index('ix_suggestions_title_cost_format', 'title', 'cost', 'format')
    )
