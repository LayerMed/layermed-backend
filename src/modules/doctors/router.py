from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_current_doctor, get_current_user
from src.core.enums import UserRole
from src.core.logs import logger
from src.core.redis import RedisCache, get_redis
from src.core.schemas import PasswordConfirm
from src.modules.doctors.schemas import (
    DoctorCreate,
    DoctorFilterParams,
    DoctorRead,
    DoctorUpdate,
)
from src.modules.doctors.service import (
    delete_doctor,
    get_doctor_by_id,
    get_doctors_by_filters,
    register_doctor,
    update_doctor,
)
from src.modules.users.schemas import UserRead

router = APIRouter(prefix="/doctors", tags=["Doctors"])


# CREATE
@router.post(
    "/register",
    response_model=DoctorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registering a doctor account",
)
async def register_doctor_handle(
    new_doctor: DoctorCreate,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorRead:
    if current_user.role == UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor profile already exists",
        )

    doctor = await register_doctor(new_doctor, current_user, db, redis)
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more specialties not found or database conflict",
        )

    return doctor


# READ
@router.get(
    "/",
    response_model=list[DoctorRead],
    summary="Get all doctor from databse by filters",
)
async def get_doctors_by_filters_handle(
    filters: Annotated[DoctorFilterParams, Depends()],
    db: AsyncSession = Depends(get_session),
) -> list[DoctorRead]:
    doctors = await get_doctors_by_filters(filters, db)
    return doctors


@router.get("/{doctor_id}", response_model=DoctorRead, summary="Get doctor by id")
async def get_doctor_by_id_handle(
    doctor_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorRead:
    doctor = await get_doctor_by_id(doctor_id, db, redis)
    if doctor is None:
        logger.warning(
            "Doctor with id {doctor_id} not found",
            doctor_id=doctor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )
    return doctor


# UPDATE
@router.patch(
    "/me", response_model=DoctorRead, summary="Update doctor profile informaiton"
)
async def update_doctor_basic_handle(
    doctor_data: DoctorUpdate,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorRead:
    updated_doctor = await update_doctor(
        doctor_data, current_doctor, current_user, db, redis
    )
    return updated_doctor


# DELETE
@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete doctor profile",
)
async def delete_doctor_account_handle(
    password_data: PasswordConfirm,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> None:
    result = await delete_doctor(password_data, current_doctor, current_user, db, redis)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
