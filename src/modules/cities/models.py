from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.services.storage.postgres import Base, IdMixin, Timestamp


class City(Base, IdMixin, Timestamp):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(unique=True)

    user: Mapped[list["User"]] = relationship(back_populates="city")
    offers: Mapped[list["Offer"]] = relationship(back_populates="city")
