from enum import Enum


class UserRole(str, Enum):
    CLIENT = "client"
    DOCTOR = "doctor"
    ADMIN = "admin"
