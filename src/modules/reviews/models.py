from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.enums import ModerationStatus
from src.services.storage.postgres import Base, Timestamp


class Review(Base, Timestamp):
    __tablename__ = "reviews"

    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[int]
    comment: Mapped[str]
    status: Mapped[ModerationStatus] = mapped_column(default=ModerationStatus.PENDING)
    # Сделать логику модерации оставляемых пользователями отзывов

    doctor: Mapped["Doctor"] = relationship(back_populates="reviews")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("doctor_id", "user_id", name="uq_reviews_doctor_user"),
    )
