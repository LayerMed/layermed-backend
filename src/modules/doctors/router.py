from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.enums import UserRole
from src.common.schemas import PaginatedResponse, PasswordConfirm
from src.core.dependencies import get_admin_user, get_current_doctor, get_current_user, get_optional_user
from src.modules.doctors.exceptions import DoctorNotFoundError, DoctorProfileAlreadyExistsError
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
    delete_doctor_avatar,
    get_doctor_by_id,
    get_doctors_by_filters,
    register_doctor,
    update_doctor,
    upload_doctor_avatar,
)
from src.modules.users.schemas import UserRead
from src.services.moderation.service import approve_item, reject_item
from src.services.storage.postgres import get_session
from src.services.storage.redis import RedisCache, get_redis

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


@router.post(
    "/avatar", status_code=status.HTTP_201_CREATED, summary="Upload doctor avatar"
)
async def upload_doctor_avatar_handle(
    image: UploadFile = File(...),
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> str:
    return await upload_doctor_avatar(image, current_doctor, db, redis)


# READ
@router.get(
    "/",
    response_model=PaginatedResponse[DoctorRead],
    summary="Get all doctor from databse by filters",
)
async def get_doctors_by_filters_handle(
    filters: Annotated[DoctorFilterParams, Depends()],
    optional_user: UserRead | None = Depends(get_optional_user),
    specialty_ids: Annotated[list[int] | None, Query()] = None,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> PaginatedResponse[DoctorRead]:
    return await get_doctors_by_filters(filters, optional_user, specialty_ids, db, redis)


@router.get(
    "/me",
    response_model=DoctorReadDetailed,
    summary="Get current doctor profile (including application status and rejection reason)",
)
async def get_current_doctor_profile_handle(
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorReadDetailed:
    if not current_user.doctor:
        raise DoctorNotFoundError()
    return await get_doctor_by_id(current_user.doctor.id, current_user, db, redis)


@router.get(
    "/{doctor_id}", response_model=DoctorReadDetailed, summary="Get doctor by id"
)
async def get_doctor_by_id_handle(
    doctor_id: int,
    optional_user: UserRead | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorReadDetailed:
    return await get_doctor_by_id(doctor_id, optional_user, db, redis)



# UPDATE
@router.patch(
    "/me", response_model=DoctorRead, summary="Update doctor profile informaiton"
)
async def update_doctor_basic_handle(
    doctor_data: DoctorUpdate,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> DoctorRead:
    return await update_doctor(doctor_data, current_doctor, db, redis)


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
    return await approve_item(
        Doctor, DoctorRead, doctor_id, db, redis, ["doctors", "users"]
    )


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
        ["doctors", "users"],
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


@router.delete(
    "/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete doctor avatar",
)
async def delete_doctor_avatar_handle(
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> None:
    await delete_doctor_avatar(current_doctor, db, redis)
