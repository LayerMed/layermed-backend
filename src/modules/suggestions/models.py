from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base, Timestamp


class Suggest(Base, Timestamp):
    __tablename__ = 'suggestions'

    doctor_id: Mapped[int] = mapped_column(
        ForeignKey('doctors.id', ondelete='cascade')
    )
    title: Mapped[str]
    description: Mapped[str]
    cost: Mapped[int]
    suggest_format: Mapped[str]
    duration: Mapped[int]

    __table_args__ = (
        Index('ix_suggestions_title_cost_format', 'title', 'cost', 'suggest_format'),
    )

    bookings: Mapped[list['Booking']] = relationship(back_populates='suggestion')
    doctor: Mapped['Doctor'] = relationship(back_populates='suggestions')
