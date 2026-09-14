import sqlalchemy.exc
from fastapi import UploadFile
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.common.enums import CacheTTL, ModerationStatus, S3Folders, UserRole
from src.common.schemas import PaginatedResponse, PasswordConfirm
from src.core.security import verify_pwd
from src.modules.doctors.exceptions import (
    DoctorNotFoundError,
    DoctorPendingError,
    DoctorProfileAlreadyExistsError,
    IncorrectPasswordError,
    SpecialtiesNotFoundError,
)
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import (
    DoctorCreate,
    DoctorFilterParams,
    DoctorRead,
    DoctorReadDetailed,
    DoctorUpdate,
)
from src.modules.specialties.models import Specialty
from src.modules.users.models import User
from src.modules.users.schemas import UserRead
from src.modules.users.service import get_user_password
from src.services.images.service import (
    avatar_optimization,
    save_and_upload_image,
)
from src.services.storage.redis import RedisCache
from src.services.storage.s3 import delete_image


def check_doctor_status(current_doctor: DoctorRead) -> None:
    if not current_doctor.status == ModerationStatus.APPROVED:
        raise DoctorPendingError()


# CREATE
async def register_doctor(
    new_doctor: DoctorCreate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> DoctorReadDetailed:
    try:
        specialties_list = []

        if new_doctor.specialty_ids:
            specialties_query = select(Specialty).where(
                Specialty.id.in_(new_doctor.specialty_ids)
            )
            specialties_result = await db.execute(specialties_query)
            specialties_list = list(specialties_result.scalars().all())

            if len(specialties_list) != len(set(new_doctor.specialty_ids)):
                raise SpecialtiesNotFoundError()

        doctor = Doctor(
            user_id=current_user.id,
            education=new_doctor.education,
            degree=new_doctor.degree,
            experience_years=new_doctor.experience_years,
            bio=new_doctor.bio,
            clinic=new_doctor.clinic,
            avatar_url=new_doctor.avatar_url,
            specialties=specialties_list,
        )
        db.add(doctor)

        await db.execute(
            update(User).where(User.id == current_user.id).values(role=UserRole.DOCTOR)
        )

        await db.commit()
        query = (
            select(Doctor)
            .where(Doctor.id == doctor.id)
            .options(selectinload(Doctor.specialties))
        )
        result = await db.execute(query)
        doctor = result.scalar_one()

        await redis.invalidate("doctors")
        return DoctorReadDetailed.model_validate(doctor)

    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise DoctorProfileAlreadyExistsError()


async def upload_doctor_avatar(
    image: UploadFile, current_doctor: DoctorRead, db: AsyncSession, redis: RedisCache
):
    try:
        key = await save_and_upload_image(image, S3Folders.DOCTORS, avatar_optimization)
        old_key = current_doctor.avatar_url

        query = (
            update(Doctor)
            .where(Doctor.id == current_doctor.id)
            .values(avatar_url=key)
            .returning(Doctor.avatar_url)
        )
        result = await db.execute(query)
        updated_avatar = result.scalar_one_or_none()

        if updated_avatar is None:
            await db.rollback()
            await delete_image(key)
            raise DoctorNotFoundError()

        await delete_image(old_key)

        await db.commit()

        await redis.invalidate("doctors")
        await redis.invalidate("users")

        return updated_avatar
    finally:
        await image.close()


# READ
async def get_doctors_by_filters(
    filters: DoctorFilterParams,
    optional_user: UserRead | None,
    specialty_ids: list[int] | None,
    db: AsyncSession,
    redis: RedisCache,
) -> PaginatedResponse[DoctorRead]:
    is_admin = optional_user is not None and optional_user.role == UserRole.ADMIN

    if is_admin and filters.status is not None:
        target_status = filters.status
    else:
        target_status = ModerationStatus.APPROVED

    is_public_default = filters.is_default_page() and target_status == ModerationStatus.APPROVED
    cache_key = redis.build_key("doctors", "list", "default")

    if is_public_default and not is_admin:
        cached = await redis.getc(cache_key)
        if cached:
            return PaginatedResponse[DoctorRead].model_validate(cached)

    query = (
        select(Doctor)
        .where(Doctor.status == target_status)
        .options(selectinload(Doctor.user), selectinload(Doctor.specialties))
    )

    if specialty_ids:
        query = query.where(Doctor.specialties.any(Specialty.id.in_(specialty_ids)))
    if filters.experience_years is not None:
        query = query.where(Doctor.experience_years >= filters.experience_years)
    if filters.max_price is not None:
        query = query.where(Doctor.min_price <= filters.max_price)
    if filters.rating_avg is not None:
        query = query.where(Doctor.rating_avg >= filters.rating_avg)

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    doctors = result.scalars().all()

    doctors_dto = PaginatedResponse[DoctorRead](
        items=[DoctorRead.model_validate(d) for d in doctors],
        limit=filters.limit,
        offset=filters.offset,
        total=total,
    )

    if is_public_default:
        await redis.setc(cache_key, doctors_dto, CacheTTL.FAST)

    return doctors_dto


async def get_doctor_by_id(
    doctor_id: int,
    optional_user: UserRead | None,
    db: AsyncSession,
    redis: RedisCache,
) -> DoctorReadDetailed:
    is_admin = (optional_user and optional_user.role == UserRole.ADMIN)
    is_owner = (
        optional_user
        and optional_user.doctor
        and optional_user.doctor.id == doctor_id
    )

    cache_key = redis.build_key("doctors", "items", doctor_id)
    if not is_admin and not is_owner:
        cached_doctor = await redis.getc(cache_key)
        if cached_doctor:
            return DoctorReadDetailed.model_validate(cached_doctor)

    query = (
        select(Doctor)
        .where(Doctor.id == doctor_id)
        .options(selectinload(Doctor.user), selectinload(Doctor.specialties))
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()

    if doctor is None:
        raise DoctorNotFoundError()

    if doctor.status != ModerationStatus.APPROVED and not (is_admin or is_owner):
        raise DoctorNotFoundError()

    doctor_dto = DoctorReadDetailed.model_validate(doctor)

    if not (is_admin or is_owner):
        doctor_dto.rejection_reason = None

    if doctor.status == ModerationStatus.APPROVED and not (is_admin or is_owner):
        await redis.setc(cache_key, doctor_dto, CacheTTL.SLOW)

    return doctor_dto

# UPDATE
async def update_doctor(
    doctor_data: DoctorUpdate,
    current_doctor: DoctorRead,
    db: AsyncSession,
    redis: RedisCache,
) -> DoctorRead:
    check_doctor_status(current_doctor)
    query = (
        select(Doctor)
        .where(Doctor.id == current_doctor.id)
        .options(selectinload(Doctor.user), selectinload(Doctor.specialties))
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()

    if doctor is None:
        raise DoctorNotFoundError()

    update_data = doctor_data.model_dump(exclude_unset=True)
    if not update_data:
        return DoctorRead.model_validate(doctor)

    if "specialty_ids" in update_data:
        new_ids = update_data.pop("specialty_ids")

        if new_ids:
            spec_query = select(Specialty).where(Specialty.id.in_(new_ids))
            spec_result = await db.execute(spec_query)
            specialties_list = list(spec_result.scalars().all())

            if len(specialties_list) != len(set(new_ids)):
                raise SpecialtiesNotFoundError()

            doctor.specialties = specialties_list
        else:
            doctor.specialties = []

    for key, value in update_data.items():
        setattr(doctor, key, value)

    await db.commit()
    await db.refresh(doctor)

    await redis.invalidate("doctors")
    await redis.invalidate("users")

    return DoctorRead.model_validate(doctor)


# DELETE
async def delete_doctor(
    password_data: PasswordConfirm,
    current_doctor: DoctorRead,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> None:
    check_doctor_status(current_doctor)
    current_password = await get_user_password(current_user, db)

    if not verify_pwd(password_data.password, current_password):
        raise IncorrectPasswordError()

    query = delete(Doctor).where(Doctor.id == current_doctor.id).returning(Doctor)
    result = await db.execute(query)
    deleted_doctor = result.scalar_one_or_none()
    if deleted_doctor is None:
        raise DoctorNotFoundError()

    await db.execute(
        update(User).where(User.id == current_user.id).values(role=UserRole.CLIENT)
    )

    await db.commit()

    await redis.invalidate("doctors")
    await redis.invalidate("users")


async def delete_doctor_avatar(
    current_doctor: DoctorRead,
    db: AsyncSession,
    redis: RedisCache,
) -> None:
    old_key = current_doctor.avatar_url
    if not old_key:
        return

    query = update(Doctor).where(Doctor.id == current_doctor.id).values(avatar_url=None)
    await db.execute(query)
    await db.commit()

    await redis.invalidate("doctors")
    await redis.invalidate("users")

    await delete_image(old_key)
