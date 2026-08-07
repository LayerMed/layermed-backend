
from sqlalchemy import Index
from sqlalchemy.orm import Mapped
from src.core.database import Base, Timestamp


class Book(Base, Timestamp):
    __tablename__ = 'bookings'

    user_id: Mapped[int]
    doctor_id: Mapped[int]
    suggestion_id: Mapped[int]
    book_type: Mapped[str]
    status: Mapped[str]    