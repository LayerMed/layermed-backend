

from sqlalchemy.orm import Mapped, relationship
from src.core.database import Base, Timestamp


class City(Base, Timestamp):
    __tablename__ = "cities"

    id: Mapped[int]
    name: Mapped[str]

    user: Mapped["User"] = relationship(back_populates="city")
    suggestion: Mapped["Suggestion"] = relationship(back_populates="city")