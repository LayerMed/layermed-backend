from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, Timestamp


class Symptom(Base, Timestamp):
    __tablename__ = "symptoms"

    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]


class SuggestionSymptom(Base):
    __tablename__ = "suggestion_symptoms"

    id = None
    suggestion_id: Mapped[int] = mapped_column(
        ForeignKey("suggestions.id", ondelete="cascade"), primary_key=True
    )
    symptom_id: Mapped[int] = mapped_column(
        ForeignKey("symptoms.id", ondelete="cascade"), primary_key=True
    )

    __table_args__ = (Index("idx_symptom_suggestion", "symptom_id", "suggestion_id"),)
