import sqlalchemy.exc
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.enums import DoctorStatus, UserRole
from src.core.redis import RedisCache
from src.core.schemas import PaginatedResponse, PasswordConfirm
from src.core.security import verify_pwd
from src.modules.doctors.exceptions import (
    DoctorNotFoundError,
    DoctorPendingError,
    DoctorProfileAlreadyExistsError,
    DoctorRejectedError,
    IncorrectPasswordError,
    SpecialtiesNotFoundError,
)
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import (
    DoctorCreate,
    DoctorFilterParams,
    DoctorRead,
    DoctorUpdate,
)
from src.modules.specialties.models import Specialty
from src.modules.users.models import User
from src.modules.users.schemas import UserRead
from src.modules.users.service import get_user_password


def check_doctor_status(current_doctor: DoctorRead) -> None:
    if current_doctor.status == DoctorStatus.PENDING:
        raise DoctorPendingError()
    if current_doctor.status == DoctorStatus.REJECTED:
        raise DoctorRejectedError()


# CREATE
async def register_doctor(
    new_doctor: DoctorCreate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> DoctorRead:
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
        await db.refresh(doctor)

        await redis.delc(redis.build_key("users", "current", current_user.email))
        return DoctorRead.model_validate(doctor)
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise DoctorProfileAlreadyExistsError()


# READ
async def get_doctors_by_filters(
    filters: DoctorFilterParams,
    db: AsyncSession,
) -> PaginatedResponse[DoctorRead]:
    target_status = filters.status or DoctorStatus.APPROVED

    query = (
        select(Doctor)
        .where(Doctor.status == target_status) 
        .options(selectinload(Doctor.user), selectinload(Doctor.specialties))
    )
    
    if filters.specialty_id is not None:
        query = query.where(
            Doctor.specialties.any(Specialty.id == filters.specialty_id)
        )
    if filters.experience_years is not None:
        query = query.where(Doctor.experience_years >= filters.experience_years)
    if filters.max_price is not None:
        query = query.where(Doctor.min_price <= filters.max_price)    
    if filters.rating_avg is not None:
        query = query.where(Doctor.rating_avg >= filters.rating_avg)        
    if filters.status is not None:
        if filters.status == DoctorStatus.PENDING:
            query = query.where(Doctor.status == DoctorStatus.PENDING)
        if filters.status == DoctorStatus.REJECTED:
            query = query.where(Doctor.status == DoctorStatus.REJECTED)
        if filters.status == DoctorStatus.APPROVED:
            query = query.where(Doctor.status == DoctorStatus.APPROVED)

    query = query.limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    doctors = result.scalars().all()

    return PaginatedResponse[DoctorRead](
        items=[DoctorRead.model_validate(d) for d in doctors],
        limit=filters.limit,
        offset=filters.offset,
    )


async def get_doctor_by_id(
    doctor_id: int, db: AsyncSession, redis: RedisCache
) -> DoctorRead:
    cache_key = redis.build_key("doctors", "items", doctor_id)
    cached_doctor = await redis.getc(cache_key)
    if cached_doctor:
        return DoctorRead.model_validate(cached_doctor)

    query = (
        select(Doctor).where(Doctor.id == doctor_id).options(selectinload(Doctor.user))
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()
    if doctor is None:
        raise DoctorNotFoundError()

    doctor_dto = DoctorRead.model_validate(doctor)
    await redis.setc(cache_key, doctor_dto, 900)

    return doctor_dto


# UPDATE
async def update_doctor(
    doctor_data: DoctorUpdate,
    current_doctor: DoctorRead,
    current_user: UserRead,
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

    await redis.delc(redis.build_key("doctors", "items", current_doctor.id))
    await redis.delc(redis.build_key("users", "current", current_user.email))

    return DoctorRead.model_validate(doctor)


async def update_doctor_status(
    doctor_id: int,
    status: DoctorStatus,
    db: AsyncSession,
    redis: RedisCache,
    rejection_reason: str | None = None,
) -> DoctorRead:
    query = (
        update(Doctor)
        .where(Doctor.id == doctor_id)
        .values(status=status, rejection_reason=rejection_reason)
        .returning(Doctor)
    )
    result = await db.execute(query)
    updated_doctor = result.scalar_one_or_none()

    if updated_doctor is None:
        raise DoctorNotFoundError()

    await db.commit()
    await redis.invalidate("doctors")
    return DoctorRead.model_validate(updated_doctor)


async def approve_doctor(
    doctor_id: int,
    db: AsyncSession,
    redis: RedisCache,
) -> DoctorRead:
    return await update_doctor_status(
        doctor_id, DoctorStatus.APPROVED, db, redis, rejection_reason=None
    )


async def reject_doctor(
    doctor_id: int,
    rejection_reason: str | None,
    db: AsyncSession,
    redis: RedisCache,
) -> DoctorRead:
    return await update_doctor_status(
        doctor_id, DoctorStatus.REJECTED, db, redis, rejection_reason=rejection_reason
    )


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

    await redis.delc(redis.build_key("doctors", "items", current_doctor.id))
    await redis.delc(redis.build_key("users", "current", current_user.email))
