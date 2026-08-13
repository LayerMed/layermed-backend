import datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base, Timestamp
from src.core.enums import UserRole


class User(Base, Timestamp):
    __tablename__ = "users"

    name: Mapped[str]
    birth_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), nullable=True, default=None)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    role: Mapped[UserRole] = mapped_column(default=UserRole.CLIENT)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")
    doctor: Mapped[Optional["Doctor"]] = relationship(
        back_populates="user", uselist=False
    )
    city: Mapped["City"] = relationship(back_populates="user")
