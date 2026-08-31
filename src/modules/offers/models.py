from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Offer(Base, Timestamp):
    __tablename__ = "offers"

    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="cascade"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    title: Mapped[str]
    description: Mapped[str]
    cost: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)
    suggest_format: Mapped[str]
    duration: Mapped[int]

    __table_args__ = (
        Index(
            "ix_offers_title_cost_format",
            "city_id",
            "title",
            "cost",
            "suggest_format",
        ),
    )

    bookings: Mapped[list["Booking"]] = relationship(back_populates="offers")
    doctor: Mapped["Doctor"] = relationship(back_populates="offers")
    city: Mapped["City"] = relationship(back_populates="offers")
