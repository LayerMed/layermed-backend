
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base, Timestamp


class Book(Base, Timestamp):
    __tablename__ = 'bookings'

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete='cascade')
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete='cascade')
    )
    suggestion_id: Mapped[int] = mapped_column(
        ForeignKey("suggestions.id", ondelete='cascade')
    )
    book_type: Mapped[str]
    status: Mapped[str]    