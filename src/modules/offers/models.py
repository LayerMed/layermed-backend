from sqlalchemy import ARRAY, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp
from src.core.enums import ModerationStatus, OfferFormat


class Offer(Base, Timestamp):
    __tablename__ = "offers"

    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="cascade"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    title: Mapped[str]
    description: Mapped[str]
    cost: Mapped[int]
    status: Mapped[ModerationStatus] = mapped_column(default=ModerationStatus.PENDING)
    rejection_reason: Mapped[str | None] = mapped_column(nullable=True, default=None)
    offer_format: Mapped[OfferFormat]
    images: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True, default=None
    )

    __table_args__ = (
        Index(
            "ix_offers_title_cost_format",
            "city_id",
            "title",
            "cost",
            "offer_format",
        ),
    )

    bookings: Mapped[list["Booking"]] = relationship(back_populates="offer")
    doctor: Mapped["Doctor"] = relationship(back_populates="offers")
    city: Mapped["City"] = relationship(back_populates="offers")
