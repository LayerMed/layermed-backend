from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Doctor(Base, Timestamp):
    __tablename__ = "doctors"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="cascade"), unique=True
    )
    education: Mapped[str]
    degree: Mapped[str | None] = mapped_column(nullable=True, default=None)
    experience_years: Mapped[int]
    bio: Mapped[str]
    min_price: Mapped[int] = mapped_column(default=0)
    clinic: Mapped[str]
    avatar_url: Mapped[str | None] = mapped_column(nullable=True, default=None)
    rating_avg: Mapped[float] = mapped_column(default=0.0)
    reviews_count: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        Index("ix_doctors_speciality_exp", "education", "experience_years"),
    )

    user: Mapped["User"] = relationship(back_populates="doctor")
    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="doctor")
    specialties: Mapped[list["Specialty"]] = relationship(
        back_populates="doctors", secondary="doctor_specialties"
    )    
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )

    @property
    def specialty_ids(self) -> list[int]:
        return [s.id for s in self.specialties] if self.specialties else []
