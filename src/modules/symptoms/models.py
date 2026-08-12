
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, Timestamp


class Symptom(Base, Timestamp):
    __tablename__ = "symptoms"

    name: Mapped[str]
    description: Mapped[str]


class SuggestionSymtom(Base):
    __tablename__ = "suggestion_symptoms"

    id = None
    suggestion_id: Mapped[int] = mapped_column(ForeignKey("suggestions.id", ondelete='cascade'), primary_key=True)
    symptome_id: Mapped[int] = mapped_column(ForeignKey("symptoms.id", ondelete="cascade"), primary_key=True)

