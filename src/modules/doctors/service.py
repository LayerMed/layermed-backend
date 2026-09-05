import sqlalchemy.exc
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.enums import CacheTTL, ModerationStatus, UserRole
from src.core.redis import RedisCache
from src.core.schemas import PaginatedResponse, PasswordConfirm
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


# READ
async def get_doctors_by_filters(
    filters: DoctorFilterParams,
    specialty_ids: list[int] | None,
    db: AsyncSession,
    redis: RedisCache,
) -> PaginatedResponse[DoctorRead]:
    is_default = filters.is_default_page()
    cache_key = redis.build_key("doctors", "list", "default")

    if is_default:
        cached = await redis.getc(cache_key)
        if cached:
            return PaginatedResponse[DoctorRead].model_validate(cached)

    target_status = filters.status or ModerationStatus.APPROVED
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

    query = query.limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    doctors = result.scalars().all()

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = (await db.execute(count_query)).scalar_one()

    doctors_dto = PaginatedResponse[DoctorRead](
        items=[DoctorRead.model_validate(d) for d in doctors],
        limit=filters.limit,
        offset=filters.offset,
        total=total
    )

    if is_default:
        await redis.setc(cache_key, doctors_dto, CacheTTL.FAST)

    return doctors_dto


async def get_doctor_by_id(
    doctor_id: int, db: AsyncSession, redis: RedisCache
) -> DoctorReadDetailed:
    cache_key = redis.build_key("doctors", "items", doctor_id)
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

    doctor_dto = DoctorReadDetailed.model_validate(doctor)
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
