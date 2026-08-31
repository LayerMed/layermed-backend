import datetime

from pydantic import BaseModel, ConfigDict

from src.core.enums import BookingStatus


class BookingCreate(BaseModel):
    offer_id: int
    appointment_time: datetime.datetime


class BookingRead(BaseModel):
    id: int
    user_id: int
    offer_id: int
    status: BookingStatus
    appointment_time: datetime.datetime
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
