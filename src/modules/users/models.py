import datetime
from typing import Optional

from sqlalchemy import Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import UserRole
from src.core.database import Base, Timestamp


class User(Base, Timestamp):
    __tablename__ = "users"
    name: Mapped[str]
    age: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    role: Mapped[UserRole] = mapped_column(default=UserRole.CLIENT)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")
    doctor: Mapped[Optional["Doctor"]] = relationship(back_populates="user", uselist=False)
