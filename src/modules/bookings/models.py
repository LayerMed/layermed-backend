import datetime

from sqlalchemy import TIMESTAMP, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import BookStatus
from src.core.database import Base, Timestamp


class Booking(Base, Timestamp):
    __tablename__ = "bookings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="cascade"))
    suggestion_id: Mapped[int] = mapped_column(
        ForeignKey("suggestions.id", ondelete="cascade")
    )
    status: Mapped[BookStatus] = mapped_column(default=BookStatus.PENDING)
    appointment_time: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="bookings")
    suggestion: Mapped["Suggestion"] = relationship(back_populates="bookings")
