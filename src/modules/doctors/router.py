from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_current_doctor, get_current_user
from src.core.logs import logger
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead, DoctorCreate, DoctorUpdate
from src.modules.doctors.service import (
    delete_doctor,
    get_doctor_by_id,
    get_doctors_by_filters,
    register_doctor,
    update_doctor,
)
from src.modules.users.models import User
from src.modules.users.schemas import DoctorFilterParams, PasswordConfirm

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    if current_user.role == "doctor":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor profile already exists",
        )
    doctor = await register_doctor(new_doctor, current_user, db)
    return doctor


# READ
@router.get("/", response_model=list[DoctorRead], summary="Get all doctor from databse")
async def get_doctors_by_filters_handle(
    filters: Annotated[DoctorFilterParams, Depends()],
    db: AsyncSession = Depends(get_session),
):
    doctors = await get_doctors_by_filters(filters, db)
    return doctors


@router.get("/{doctor_id}", response_model=DoctorRead, summary="Get doctor by id")
async def get_doctor_by_id_handle(
    doctor_id: int,
    db: AsyncSession = Depends(get_session),
):
    doctor = await get_doctor_by_id(doctor_id, db)
    if doctor is None:
        logger.warning(
            "Failed to fetch doctor: Doctor with id {doctor_id} not found",
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
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
):
    logger.debug(
        "Doctor ID:{id}, was update with params: {specialty_id},  {education}, {experience_years}",
        specialty_id=current_doctor.specialty_id,
        education=current_doctor.education,
        experience_years=current_doctor.experience_years,
        id=current_doctor.id,
    )
    updated_doctor = await update_doctor(doctor_data, current_doctor, db)
    return updated_doctor


# DELETE
@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete doctor profile",
)
async def delete_doctor_account_handle(
    password_data: PasswordConfirm,
    current_user: User = Depends(get_current_user),
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
):
    result = await delete_doctor(password_data, current_doctor, current_user, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
