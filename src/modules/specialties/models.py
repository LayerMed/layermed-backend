from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Specialty(Base, Timestamp):
    __tablename__ = "specialties"

    name: Mapped[str]
    description: Mapped[str]

    doctors: Mapped[list["Doctor"]] = relationship(
        secondary="doctor_specialties", back_populates="specialties"
    )


class DoctorSpecialty(Base, Timestamp):
    __tablename__ = "doctor_specialties"

    id = None
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="cascade"), primary_key=True
    )
    specialty_id: Mapped[int] = mapped_column(
        ForeignKey("specialties.id", ondelete="cascade"), primary_key=True
    )
