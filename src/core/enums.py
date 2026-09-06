from enum import IntEnum, StrEnum


class UserRole(StrEnum):
    CLIENT = "client"
    DOCTOR = "doctor"
    ADMIN = "admin"


class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class ModerationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OfferFormat(StrEnum):
    CLINIC = "clinic"
    ONLINE = "online"
    HOME_VISIT = "home_visit"
    CHAT = "chat"


class CacheTTL(IntEnum):
    STATIC = 60 * 60 * 24 * 30
    SLOW = 60 * 60 * 12        
    FAST = 60 * 15             
    MOMENTARY = 60 * 2         


class S3Folders(StrEnum):
    DOCTORS = "doctors"
    OFFERS = "offers"