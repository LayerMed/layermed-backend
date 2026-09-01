from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user, get_current_doctor, get_current_user
from src.core.enums import UserRole
from src.core.moderation.service import approve_item, reject_item
from src.core.redis import RedisCache, get_redis
from src.core.schemas import PaginatedResponse, PasswordConfirm
from src.modules.doctors.exceptions import DoctorProfileAlreadyExistsError
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import (
    DoctorCreate,
    DoctorFilterParams,
    DoctorRead,
    DoctorReadDetailed,
    DoctorReject,
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
    response_model=DoctorReadDetailed,
    status_code=status.HTTP_201_CREATED,
    summary="Registering a doctor account",
)
async def register_doctor_handle(
    new_doctor: DoctorCreate,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorReadDetailed:
    if current_user.role == UserRole.DOCTOR:
        raise DoctorProfileAlreadyExistsError()
    return await register_doctor(new_doctor, current_user, db, redis)


# READ
@router.get(
    "/",
    response_model=PaginatedResponse[DoctorRead],
    summary="Get all doctor from databse by filters",
)
async def get_doctors_by_filters_handle(
    filters: Annotated[DoctorFilterParams, Depends()],
    db: AsyncSession = Depends(get_session),
) -> PaginatedResponse[DoctorRead]:
    return await get_doctors_by_filters(filters, db)


@router.get(
    "/{doctor_id}", response_model=DoctorReadDetailed, summary="Get doctor by id"
)
async def get_doctor_by_id_handle(
    doctor_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorReadDetailed:
    return await get_doctor_by_id(doctor_id, db, redis)


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
    return await update_doctor(doctor_data, current_doctor, current_user, db, redis)


@router.patch(
    "/{doctor_id}/approve",
    response_model=DoctorRead,
    summary="Approve doctor application (Admin only)",
)
async def approve_doctor_handle(
    doctor_id: int,
    admin: UserRead = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorRead:
    return await approve_item(Doctor, DoctorRead, doctor_id, db, redis, "doctors")


@router.patch(
    "/{doctor_id}/reject",
    response_model=DoctorRead,
    summary="Reject doctor application (Admin only)",
)
async def reject_doctor_handle(
    doctor_id: int,
    reject_data: DoctorReject,
    admin: UserRead = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorRead:
    return await reject_item(
        Doctor,
        DoctorRead,
        doctor_id,
        db,
        redis,
        reject_data.rejection_reason,
        "doctors",
    )


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
    await delete_doctor(password_data, current_doctor, current_user, db, redis)
