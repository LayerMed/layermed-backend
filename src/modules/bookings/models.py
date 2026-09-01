import datetime

from sqlalchemy import TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp
from src.core.enums import BookingStatus


class Booking(Base, Timestamp):
    __tablename__ = "bookings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="cascade"))
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="cascade"))
    status: Mapped[BookingStatus] = mapped_column(default=BookingStatus.PENDING)
    appointment_time: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="bookings")
    offer: Mapped["Offer"] = relationship(back_populates="bookings")
