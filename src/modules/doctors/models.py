
from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base, Timestamp


class Doctor(Base, Timestamp):
    __tablename__ = 'doctors'
    user_id: Mapped[int]
    speciality: Mapped[str]
    educational: Mapped[str] 
    experience_years: Mapped[int]
    bio: Mapped[str]

    __table_args__ = (
        Index('ix_doctors_speciality_exp', 'speciality', 'educational', 'experience_years')
    )