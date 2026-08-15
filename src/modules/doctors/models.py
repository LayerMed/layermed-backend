from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Doctor(Base, Timestamp):
    __tablename__ = "doctors"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="cascade"), unique=True
    )
    specialty_id: Mapped[int]
    education: Mapped[str]
    experience_years: Mapped[int]
    bio: Mapped[str]

    __table_args__ = (
        Index(
            "ix_doctors_speciality_exp", "specialty_id", "education", "experience_years"
        ),
    )

    user: Mapped["User"] = relationship(back_populates="doctor")
    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="doctor")
    specialties: Mapped[list["Specialty"]] = relationship(
        back_populates="doctors", secondary="doctor_specialties"
    )
