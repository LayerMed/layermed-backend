from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp
from src.core.enums import DoctorStatus


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
    status: Mapped[DoctorStatus] = mapped_column(default=DoctorStatus.PENDING)
    rejection_reason: Mapped[str | None] = mapped_column(nullable=True, default=None)

    __table_args__ = (
        Index("ix_doctors_speciality_exp", "education", "experience_years"),
    )

    user: Mapped["User"] = relationship(back_populates="doctor")
    offers: Mapped[list["Offer"]] = relationship(back_populates="doctor")
    specialties: Mapped[list["Specialty"]] = relationship(
        back_populates="doctors", secondary="doctor_specialties"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
