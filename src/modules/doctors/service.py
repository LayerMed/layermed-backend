from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.enums import UserRole
from src.core.schemas import PasswordConfirm
from src.core.security import verify_pwd
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorCreate, DoctorFilterParams, DoctorUpdate
from src.modules.users.models import User


# CREATE
async def register_doctor(
    new_doctor: DoctorCreate,
    current_user: User,
    db: AsyncSession,
) -> Doctor:
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
    await db.refresh(doctor)
    return doctor


# READ
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


async def get_doctor_by_id(doctor_id: int, db: AsyncSession) -> Doctor | None:
    query = (
        select(Doctor).where(Doctor.id == doctor_id).options(selectinload(Doctor.user))
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()
    return doctor


# UPDATE
async def update_doctor(
    doctor_data: DoctorUpdate,
    current_doctor: Doctor,
    db: AsyncSession,
) -> Doctor:
    update_data = doctor_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_doctor, field, value)

    await db.commit()
    return current_doctor


# DELETE
async def delete_doctor(
    password_data: PasswordConfirm,
    current_doctor: Doctor,
    db: AsyncSession,
) -> bool:

    user = current_doctor.user
    if not verify_pwd(password_data.password, user.password):
        return False

    user.role = UserRole.CLIENT

    await db.delete(current_doctor)

    await db.commit()

    return True
