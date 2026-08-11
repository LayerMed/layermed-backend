from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Doctor(Base, Timestamp):
    __tablename__ = "doctors"
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="cascade"), unique=True
    )
    speciality: Mapped[str]
    educational: Mapped[str]
    experience_years: Mapped[int]
    bio: Mapped[str]

    __table_args__ = (
        Index(
            "ix_doctors_speciality_exp", "speciality", "educational", "experience_years"
        ),
    )

    user: Mapped["User"] = relationship(back_populates="doctor")
    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="doctor")
