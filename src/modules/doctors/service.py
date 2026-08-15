from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.enums import UserRole
from src.core.security import verify_pwd
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRegister, DoctorUpdate
from src.modules.users.models import User
from src.modules.users.schemas import DoctorFilterParams, PasswordConfirm


async def register_doctor(
    new_doctor: DoctorRegister,
    current_user: User,
    db: AsyncSession,
):
    doctor = Doctor(
        user_id=current_user.id,
        specialty_id=new_doctor.specialty_id,
        education=new_doctor.education,
        experience_years=new_doctor.experience_years,
        bio=new_doctor.bio,
    )
    current_user.role = UserRole.DOCTOR
    db.add(doctor)

    await db.commit()
    doctor.user = current_user
    return doctor


async def update_doctor(
    doctor_data: DoctorUpdate,
    current_doctor: Doctor,
    db: AsyncSession,
):
    update_data = doctor_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_doctor, field, value)

    await db.commit()
    return current_doctor


async def delete_doctor(
    password_data: PasswordConfirm,
    current_doctor: Doctor,
    current_user: User,
    db: AsyncSession,
):
    if not verify_pwd(password_data.password, current_user.password):
        return False

    current_user.role = UserRole.CLIENT

    await db.delete(current_doctor)

    await db.commit()

    return True


async def get_doctors_by_filters(
    filters: DoctorFilterParams,
    db: AsyncSession,
) -> list[Doctor]:
    query = select(Doctor).options(selectinload(Doctor.user))

    if filters.specialty_id is not None:
        query = query.where(Doctor.specialty_id == filters.specialty_id)
    if filters.min_experience is not None:
        query = query.where(Doctor.experience_years >= filters.min_experience)

    query = query.offset(filters.offset).limit(filters.limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_doctor_by_id(doctor_id: int, db: AsyncSession):
    query = query = (
        select(Doctor).where(Doctor.id == doctor_id).options(selectinload(Doctor.user))
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()
    return doctor
