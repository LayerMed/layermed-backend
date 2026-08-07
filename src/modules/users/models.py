from sqlalchemy.orm import Mapped, mapped_column
from core.enums import UserRole
from src.core.database import Base, Timestamp

class User(Base, Timestamp):
    __tablename__ = 'users'
    name: Mapped[str]
    age: Mapped[int | None]
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    role: Mapped[UserRole] = mapped_column(default=UserRole.CLIENT)