import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from PIL import Image
from sqlalchemy import select

from src.common.enums import CacheTTL, ModerationStatus, UserRole
from src.core.security import hash_pwd
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead
from src.modules.specialties.models import Specialty
from src.modules.users.models import User


class TestRegisterDoctor:
    async def test_register_doctor(self, ac, get_test_session, fake_get_current_user):
        doctor_data = {
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Board-certified cardiologist specializing in preventive cardiology, non-invasive imaging, and hypertension management with over a decade of clinical practice",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 201
        data = response.json()

        query = select(Doctor).where(Doctor.id == data["id"])
        result = await get_test_session.execute(query)
        doctor = result.scalar_one_or_none()

        assert doctor.specialties == []
        assert doctor.education == "Harvard Medical School, MD (2012)"
        assert doctor.degree == "Doctor of Medicine (MD)"
        assert doctor.experience_years == 14
        assert (
            doctor.bio
            == "Board-certified cardiologist specializing in preventive cardiology, non-invasive imaging, and hypertension management with over a decade of clinical practice"
        )
        assert doctor.status == ModerationStatus.PENDING

    async def test_register_doctor_already_exists(
        self, ac, get_test_session, fake_get_current_user_as_doctor
    ):
        doctor_data = {
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Board-certified cardiologist specializing in preventive cardiology, non-invasive imaging, and hypertension management with over a decade of clinical practice",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 409

    async def test_register_doctor_specialties_not_found(
        self, ac, get_test_session, fake_get_current_user
    ):
        doctor_data = {
            "specialty_ids": [1, 90, 9999, 2],
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Board-certified cardiologist specializing in preventive cardiology, non-invasive imaging, and hypertension management with over a decade of clinical practice",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 404

    async def test_register_doctor_specialties(
        self, ac, get_test_session, fake_get_current_user
    ):
        specialty_cardiology = Specialty(
            name="Cardiology",
            description="Deals with disorders of the heart and the cardiovascular system.",
        )
        specialty_neurology = Specialty(
            name="Neurology",
            description="Specializes in the diagnosis and treatment of diseases of the brain, spinal cord, and nerves.",
        )
        get_test_session.add_all([specialty_cardiology, specialty_neurology])
        await get_test_session.commit()
        await get_test_session.refresh(specialty_cardiology)
        await get_test_session.refresh(specialty_neurology)

        doctor_data = {
            "specialty_ids": [specialty_cardiology.id, specialty_neurology.id],
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Board-certified cardiologist specializing in preventive cardiology, non-invasive imaging, and hypertension management with over a decade of clinical practice",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        data = response.json()
        assert response.status_code == 201

        query = select(Doctor).where(Doctor.id == data["id"])
        result = await get_test_session.execute(query)
        doctor = result.scalar_one_or_none()

        specialty_ids = [s.id for s in doctor.specialties]
        assert sorted(specialty_ids) == sorted(
            [specialty_cardiology.id, specialty_neurology.id]
        )

    async def test_register_doctor_cache(
        self, ac, get_test_session, fake_get_redis, fake_get_current_user
    ):
        cache_key = fake_get_redis.build_key("doctors", "list", "default")
        now = datetime.now(UTC).replace(tzinfo=None)

        existing_user = User(
            name="TestDoctor",
            email="doctor@test.com",
            password=hash_pwd("test_hashed_password"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(existing_user)
        await get_test_session.flush()

        doctor = Doctor(
            user_id=existing_user.id,
            education="Harvard Medical School, MD (2012)",
            degree="Doctor of Medicine (MD)",
            experience_years=14,
            bio="Board-certified cardiologist.",
            min_price=150,
            clinic="Boston Heart & Vascular Center",
            rating_avg=4.9,
            reviews_count=28,
            status=ModerationStatus.APPROVED,
            rejection_reason=None,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.commit()
        await get_test_session.refresh(doctor)

        doctor_dto = DoctorRead.model_validate(doctor)
        await fake_get_redis.setc(cache_key, [doctor_dto], CacheTTL.FAST)

        assert await fake_get_redis.getc(cache_key) is not None

        doctor_data = {
            "education": "Stanford Medicine, MD (2018)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 8,
            "bio": "Board-certified neurologist specializing in neuro-oncology.",
            "clinic": "Stanford Health Care",
        }

        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 201

        assert await fake_get_redis.getc(cache_key) is None


def create_test_image(
    format: str = "JPEG", size: tuple[int, int] = (100, 100)
) -> io.BytesIO:
    file = io.BytesIO()
    image = Image.new("RGB", size, color="blue")
    image.save(file, format=format)
    file.seek(0)
    return file


class TestUploadDoctorAvatar:
    async def test_upload_doctor_avatar_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        fake_get_current_user_as_doctor,
    ):
        image_stream = create_test_image(format="JPEG", size=(600, 400))
        files = {"image": ("avatar.jpg", image_stream, "image/jpeg")}

        new_s3_key = "doctors/new_avatar_uuid.jpg"

        with (
            patch(
                "src.modules.doctors.service.save_and_upload_image",
                new_callable=AsyncMock,
            ) as mock_save,
            patch(
                "src.modules.doctors.service.delete_image", new_callable=AsyncMock
            ) as mock_delete,
        ):
            mock_save.return_value = new_s3_key
            mock_delete.return_value = None

            response = await ac.post("/doctors/avatar", files=files)

        assert response.status_code == 201
        assert response.json() == new_s3_key
        mock_save.assert_awaited_once()

        current_doctor = fake_get_current_user_as_doctor.doctor

        mock_delete.assert_awaited_once_with(current_doctor.avatar_url)

        query = select(Doctor).where(Doctor.id == current_doctor.id)
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert doctor_in_db.avatar_url == new_s3_key
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert doctor_in_db.avatar_url == new_s3_key

    async def test_upload_doctor_avatar_invalid_extension(
        self,
        ac,
        fake_get_current_user_as_doctor,
    ):
        text_file = io.BytesIO(b"not an image content")
        files = {"image": ("file.txt", text_file, "text/plain")}

        response = await ac.post("/doctors/avatar", files=files)

        assert response.status_code == 415

    async def test_upload_doctor_avatar_corrupted_image_data(
        self,
        ac,
        fake_get_current_user_as_doctor,
    ):
        corrupted_data = io.BytesIO(b"fake image bytes")
        files = {"image": ("avatar.png", corrupted_data, "image/png")}

        response = await ac.post("/doctors/avatar", files=files)

        assert response.status_code == 415
