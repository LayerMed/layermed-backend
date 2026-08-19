import sqlalchemy.exc
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.enums import UserRole
from src.core.redis import RedisCache
from src.core.schemas import PasswordConfirm
from src.core.security import verify_pwd
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


async def register_doctor(
    new_doctor: DoctorCreate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> DoctorRead | None:
    try:
        specialties_list = []

        if new_doctor.specialty_ids:
            specialties_query = select(Specialty).where(
                Specialty.id.in_(new_doctor.specialty_ids)
            )
            specialties_result = await db.execute(specialties_query)
            specialties_list = list(specialties_result.scalars().all())

            if len(specialties_list) != len(set(new_doctor.specialty_ids)):
                return None

        doctor = Doctor(
            user_id=current_user.id,
            education=new_doctor.education,
            experience_years=new_doctor.experience_years,
            bio=new_doctor.bio,
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
        return None


# READ
async def get_doctors_by_filters(
    filters: DoctorFilterParams,
    db: AsyncSession,
) -> list[DoctorRead]:
    query = select(Doctor).options(selectinload(Doctor.user))

    if filters.specialty_id is not None:
        query = query.where(Doctor.specialties == filters.specialty_id)
    if filters.min_experience is not None:
        query = query.where(Doctor.experience_years >= filters.min_experience)

    query = query.offset(filters.offset).limit(filters.limit)

    result = await db.execute(query)
    doctors = result.scalars().all()
    return [DoctorRead.model_validate(d) for d in doctors]


async def get_doctor_by_id(
    doctor_id: int, db: AsyncSession, redis: RedisCache
) -> DoctorRead | None:
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
        return None

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
    update_data = doctor_data.model_dump(exclude_unset=True)

    if not update_data:
        return current_doctor

    query = (
        update(Doctor)
        .where(Doctor.id == current_doctor.id)
        .values(**update_data)
        .returning(Doctor)
    )
    result = await db.execute(query)
    updated_doctor = result.scalar_one()

    await db.commit()

    await redis.delc(redis.build_key("doctors", "items", current_doctor.id))
    await redis.delc(redis.build_key("users", "current", current_user.email))

    return DoctorRead.model_validate(updated_doctor)


# DELETE
async def delete_doctor(
    password_data: PasswordConfirm,
    current_doctor: DoctorRead,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> bool:
    if not verify_pwd(password_data.password, current_user.password):
        return False

    user_cte = (
        update(User)
        .where(User.id == current_user.id)
        .values(role=UserRole.CLIENT)
        .returning(User.id)
    ).cte("updated_user")

    query = (
        delete(Doctor)
        .where(Doctor.id == current_doctor.id)
        .where(Doctor.user_id == user_cte.c.id)
    )

    await db.execute(query)
    await db.commit()

    await redis.delc(redis.build_key("doctors", "items", current_doctor.id))
    await redis.delc(redis.build_key("users", "current", current_user.email))

    return True
