
from sqlalchemy.orm import Mapped
from src.core.database import Base, Timestamp


class Doctor(Base, Timestamp):
    __tablename__ = 'doctors'
    user_id: Mapped[int]
    speciality: Mapped[int]
    educational: Mapped[str]
    expirience_yers: Mapped[int]
    bio: Mapped[str]