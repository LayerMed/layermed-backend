from enum import Enum


class UserRole(str, Enum):
    CLIENT = "client"
    DOCTOR = "doctor"
    ADMIN = "admin"


class BookStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
