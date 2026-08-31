from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class City(Base, Timestamp):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(unique=True)

    user: Mapped[list["User"]] = relationship(back_populates="city")
    offer: Mapped[list["Offer"]] = relationship(back_populates="city")
