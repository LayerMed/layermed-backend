from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Booking(Base, Timestamp):
    __tablename__ = "bookings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="cascade"))
    suggestion_id: Mapped[int] = mapped_column(
        ForeignKey("suggestions.id", ondelete="cascade")
    )
    book_type: Mapped[str]
    status: Mapped[str]

    user: Mapped["User"] = relationship(back_populates="bookings")
    suggestion: Mapped["Suggest"] = relationship(back_populates="bookings")
