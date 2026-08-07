from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.enums import UserRole
from src.core.database import Base, Timestamp

class User(Base, Timestamp):
    __tablename__ = 'users'
    name: Mapped[str]
    age: Mapped[int | None]
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    role: Mapped[UserRole] = mapped_column(default=UserRole.CLIENT)

    bookings: Mapped[list['Booking']] = relationship(back_populates='user')
    doctor: Mapped[Optional['Doctor']] = relationship(back_populates='user')