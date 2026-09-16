from fastapi import APIRouter

from src.modules.bookings.router import router as booking_router
from src.modules.cities.router import router as city_router
from src.modules.doctors.router import router as doctor_router
from src.modules.offers.router import router as offer_router
from src.modules.reviews.router import router as review_router
from src.modules.specialties.router import router as specialty_router
from src.modules.symptoms.router import router as symptom_router
from src.modules.users.router import router as users_router

# api_router = APIRouter(prefix="/api/v1")
api_router = APIRouter()

all_routers = [
    users_router,
    symptom_router,
    city_router,
    specialty_router,
    doctor_router,
    booking_router,
    review_router,
    offer_router,
]

for router in all_routers:
    api_router.include_router(router)
