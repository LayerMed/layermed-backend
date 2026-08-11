from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Suggestion(Base, Timestamp):
    __tablename__ = "suggestions"

    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="cascade"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    title: Mapped[str]
    description: Mapped[str]
    cost: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)
    suggest_format: Mapped[str]
    duration: Mapped[int]

    __table_args__ = (
        Index("ix_suggestions_title_cost_format", "city_id", "title", "cost", "suggest_format"),
    )

    bookings: Mapped[list["Booking"]] = relationship(back_populates="suggestion")
    doctor: Mapped["Doctor"] = relationship(back_populates="suggestions")
    city: Mapped["City"] = relationship(back_populates="suggestion")
