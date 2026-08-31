from enum import Enum, IntEnum


class UserRole(str, Enum):
    CLIENT = "client"
    DOCTOR = "doctor"
    ADMIN = "admin"


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class ModerationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CacheTTL(IntEnum):
    STATIC = 60 * 60 * 24 * 30
    SLOW = 60 * 60 * 12        
    FAST = 60 * 15             
    MOMENTARY = 60 * 2         

