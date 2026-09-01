from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, Timestamp


class Symptom(Base, Timestamp):
    __tablename__ = "symptoms"

    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]


class offerSymptom(Base):
    __tablename__ = "offer_symptoms"

    id = None
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="cascade"), primary_key=True
    )
    symptom_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="cascade"), primary_key=True
    )

    __table_args__ = (Index("idx_symptom_offer", "symptom_id", "offer_id"),)
