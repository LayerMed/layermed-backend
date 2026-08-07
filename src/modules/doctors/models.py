
from sqlalchemy.orm import Mapped
from src.core.database import Base, Timestamp


class Doctor(Base, Timestamp):
    __tablename__ = 'doctors'
    user_id: Mapped[int]
    speciality: Mapped[str]
    educational: Mapped[str]
    experience_years: Mapped[int]
    bio: Mapped[str]