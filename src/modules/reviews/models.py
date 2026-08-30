from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, Timestamp


class Review(Base, Timestamp):
    __tablename__ = "reviews"

    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[int]
    comment: Mapped[str]
    status: Mapped[str]

    doctor: Mapped["Doctor"] = relationship(back_populates="reviews")
    user: Mapped["User"] = relationship()
