import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from main import app
from src.common.enums import CacheTTL, ModerationStatus, UserRole
from src.core.dependencies import get_current_user
from src.core.security import hash_pwd
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead
from src.modules.specialties.models import Specialty
from src.modules.users.models import User
from src.modules.users.schemas import UserRead


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


class TestGetDoctorsByFilters:
    @pytest.fixture
    async def seed_doctors(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        spec_cardio = Specialty(name="Cardiology", description="Heart and vascular")
        spec_neuro = Specialty(name="Neurology", description="Brain and nerves")
        get_test_session.add_all([spec_cardio, spec_neuro])
        await get_test_session.flush()

        user1 = User(
            name="TestDoctor1",
            email="doctor1@test.com",
            password=hash_pwd("test_hashed_password"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            name="TestDoctor2",
            email="doctor2@test.com",
            password=hash_pwd("test_hashed_password"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        user3 = User(
            name="TestDoctor3",
            email="doctor3@test.com",
            password=hash_pwd("test_hashed_password"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([user1, user2, user3])
        await get_test_session.flush()

        doc1 = Doctor(
            user_id=user1.id,
            education="Medical School 1",
            degree="MD",
            experience_years=10,
            bio="Bio 1",
            min_price=100,
            clinic="Clinic 1",
            rating_avg=4.8,
            reviews_count=15,
            status=ModerationStatus.APPROVED,
            specialties=[spec_cardio],
            created_at=now,
            updated_at=now,
        )
        doc2 = Doctor(
            user_id=user2.id,
            education="Medical School 2",
            degree="PhD",
            experience_years=3,
            bio="Bio 2",
            min_price=250,
            clinic="Clinic 2",
            rating_avg=4.0,
            reviews_count=5,
            status=ModerationStatus.APPROVED,
            specialties=[spec_neuro],
            created_at=now,
            updated_at=now,
        )
        doc3 = Doctor(
            user_id=user3.id,
            education="Medical School 3",
            degree="MD",
            experience_years=7,
            bio="Bio 3",
            min_price=150,
            clinic="Clinic 3",
            rating_avg=4.5,
            reviews_count=8,
            status=ModerationStatus.PENDING,
            specialties=[spec_cardio, spec_neuro],
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([doc1, doc2, doc3])
        await get_test_session.commit()

        return {
            "doctors": [doc1, doc2, doc3],
            "specialties": [spec_cardio, spec_neuro],
        }

    async def test_get_doctors_default_list(
        self,
        ac,
        fake_get_redis,
        seed_doctors,
    ):
        response = await ac.get("/doctors/")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        cache_key = fake_get_redis.build_key("doctors", "list", "default")
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert cached_data["total"] == 2

    async def test_get_doctors_returns_cached_data(
        self,
        ac,
        fake_get_redis,
    ):
        cache_key = fake_get_redis.build_key("doctors", "list", "default")
        fake_cached_payload = {
            "items": [],
            "limit": 10,
            "offset": 0,
            "total": 0,
        }
        await fake_get_redis.setc(cache_key, fake_cached_payload, CacheTTL.FAST)

        response = await ac.get("/doctors/")
        assert response.status_code == 200
        assert response.json() == fake_cached_payload

    async def test_filter_by_specialty(
        self,
        ac,
        seed_doctors,
    ):
        spec_neuro = seed_doctors["specialties"][1]
        response = await ac.get(f"/doctors/?specialty_ids={spec_neuro.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["clinic"] == "Clinic 2"

    async def test_filter_by_experience_years(
        self,
        ac,
        seed_doctors,
    ):
        response = await ac.get("/doctors/?experience_years=5")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["experience_years"] == 10

    async def test_filter_by_max_price(
        self,
        ac,
        seed_doctors,
    ):
        response = await ac.get("/doctors/?max_price=200")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["min_price"] == 100

    async def test_filter_by_rating_avg(
        self,
        ac,
        seed_doctors,
    ):
        response = await ac.get("/doctors/?rating_avg=4.5")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["rating_avg"] == 4.8

    async def test_filter_by_status(
        self,
        ac,
        seed_doctors,
    ):
        response = await ac.get("/doctors/?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["clinic"] == "Clinic 3"

    async def test_pagination_limit_offset(
        self,
        ac,
        seed_doctors,
    ):
        response = await ac.get("/doctors/?limit=1&offset=1")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1
        assert data["limit"] == 1
        assert data["offset"] == 1


class TestDoctorById:
    @pytest.fixture
    async def persisted_doctor(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        specialty = Specialty(
            name="Cardiology",
            description="Heart care",
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(specialty)
        await get_test_session.flush()

        user = User(
            name="Doctor Bob",
            email="doctor_bob@test.com",
            password=hash_pwd("test_hashed_password"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(user)
        await get_test_session.flush()

        doctor = Doctor(
            user_id=user.id,
            education="Harvard Medical School",
            degree="MD",
            experience_years=12,
            bio="Experienced cardiologist.",
            min_price=200,
            clinic="Cardio Care Clinic",
            rating_avg=4.9,
            reviews_count=35,
            status=ModerationStatus.APPROVED,
            specialties=[specialty],
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.commit()
        await get_test_session.refresh(doctor)

        return doctor

    async def test_get_doctor_by_id_success(
        self,
        ac,
        persisted_doctor,
        fake_get_redis,
    ):
        response = await ac.get(f"/doctors/{persisted_doctor.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == persisted_doctor.id
        assert data["clinic"] == persisted_doctor.clinic
        assert data["education"] == persisted_doctor.education
        assert len(data["specialties"]) == 1
        assert data["specialties"][0]["name"] == "Cardiology"

        cache_key = fake_get_redis.build_key("doctors", "items", persisted_doctor.id)
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert cached_data["id"] == persisted_doctor.id

    async def test_get_doctor_by_id_returns_cached_data(
        self,
        ac,
        fake_get_redis,
    ):
        doctor_id = 777
        cache_key = fake_get_redis.build_key("doctors", "items", doctor_id)
        fake_cached_doctor = {
            "id": doctor_id,
            "user_id": 999,
            "education": "Cached University",
            "degree": "Professor",
            "experience_years": 20,
            "bio": "From Redis",
            "min_price": 500,
            "clinic": "Fast Cache Clinic",
            "avatar_url": None,
            "rating_avg": 5.0,
            "reviews_count": 100,
            "status": ModerationStatus.APPROVED,
            "rejection_reason": None,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "specialties": [],
        }
        await fake_get_redis.setc(cache_key, fake_cached_doctor, CacheTTL.SLOW)

        response = await ac.get(f"/doctors/{doctor_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == doctor_id
        assert data["clinic"] == "Fast Cache Clinic"
        assert data["bio"] == "From Redis"

    async def test_get_doctor_by_id_not_found(
        self,
        ac,
    ):
        response = await ac.get("/doctors/9999")
        assert response.status_code == 404


class TestDoctorModeration:
    @pytest.fixture
    async def pending_doctor(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        user = User(
            name="Pending Doctor",
            email="pending_doc@test.com",
            password=hash_pwd("test_hashed_password"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(user)
        await get_test_session.flush()

        doctor = Doctor(
            user_id=user.id,
            education="Medical Academy",
            degree="MD",
            experience_years=5,
            bio="Awaiting review.",
            min_price=100,
            clinic="Pending Clinic",
            status=ModerationStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.commit()
        await get_test_session.refresh(doctor)

        return doctor

    async def test_approve_doctor_success(
        self,
        ac,
        get_test_session,
        fake_get_admin_user,
        fake_get_redis,
        pending_doctor,
    ):
        cache_key = fake_get_redis.build_key("doctors", "items", pending_doctor.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        response = await ac.patch(f"/doctors/{pending_doctor.id}/approve")
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == pending_doctor.id
        assert data["status"] == ModerationStatus.APPROVED
        assert data["rejection_reason"] is None

        query = select(Doctor).where(Doctor.id == pending_doctor.id)
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert doctor_in_db.status == ModerationStatus.APPROVED
        assert doctor_in_db.rejection_reason is None
        assert await fake_get_redis.getc(cache_key) is None

    async def test_approve_doctor_unauthorized(
        self,
        ac,
        pending_doctor,
    ):
        response = await ac.patch(f"/doctors/{pending_doctor.id}/approve")
        assert response.status_code == 401

    async def test_approve_doctor_not_found(
        self,
        ac,
        fake_get_admin_user,
    ):
        response = await ac.patch("/doctors/9999/approve")
        assert response.status_code == 404

    async def test_reject_doctor_success(
        self,
        ac,
        get_test_session,
        fake_get_admin_user,
        fake_get_redis,
        pending_doctor,
    ):
        cache_key = fake_get_redis.build_key("doctors", "items", pending_doctor.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        payload = {"rejection_reason": "Incomplete medical license documents provided"}
        response = await ac.patch(f"/doctors/{pending_doctor.id}/reject", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == pending_doctor.id
        assert data["status"] == ModerationStatus.REJECTED
        assert data["rejection_reason"] == payload["rejection_reason"]

        query = select(Doctor).where(Doctor.id == pending_doctor.id)
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert doctor_in_db.status == ModerationStatus.REJECTED
        assert doctor_in_db.rejection_reason == payload["rejection_reason"]
        assert await fake_get_redis.getc(cache_key) is None

    async def test_reject_doctor_validation_error(
        self,
        ac,
        fake_get_admin_user,
        pending_doctor,
    ):
        payload = {}
        response = await ac.patch(f"/doctors/{pending_doctor.id}/reject", json=payload)
        assert response.status_code == 422

    async def test_reject_doctor_unauthorized(
        self,
        ac,
        pending_doctor,
    ):
        payload = {"rejection_reason": "No access"}
        response = await ac.patch(f"/doctors/{pending_doctor.id}/reject", json=payload)
        assert response.status_code == 401


class TestDoctorUpdate:
    @pytest.fixture
    async def pending_doctor_user(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        user = User(
            name="Pending Doctor",
            email="pending_doc@test.com",
            password=hash_pwd("fake_password_secret"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(user)
        await get_test_session.flush()

        doctor = Doctor(
            user_id=user.id,
            education="Initial Medical University",
            degree="MD",
            experience_years=5,
            bio="Initial bio.",
            clinic="Main Clinic",
            status=ModerationStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.commit()

        stmt = select(User).where(User.id == user.id).options(joinedload(User.doctor))
        res = await get_test_session.execute(stmt)
        full_user = res.scalar_one()

        user_read = UserRead.model_validate(full_user)

        app.dependency_overrides[get_current_user] = lambda: user_read
        yield user_read
        app.dependency_overrides.pop(get_current_user, None)
        
    async def test_update_doctor_basic_fields_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        fake_get_current_user_as_doctor,
    ):
        doctor_id = fake_get_current_user_as_doctor.doctor.id
        cache_key = fake_get_redis.build_key("doctors", "items", doctor_id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.SLOW)

        payload = {
            "education": "Updated Medical Academy",
            "experience_years": 16,
            "bio": "Updated bio text.",
        }

        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == doctor_id
        assert data["education"] == payload["education"]
        assert data["experience_years"] == payload["experience_years"]
        assert data["bio"] == payload["bio"]

        query = select(Doctor).where(Doctor.id == doctor_id)
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert doctor_in_db.education == payload["education"]
        assert doctor_in_db.experience_years == payload["experience_years"]
        assert doctor_in_db.bio == payload["bio"]
        assert await fake_get_redis.getc(cache_key) is None

    async def test_update_doctor_specialties_replace(
        self,
        ac,
        get_test_session,
        fake_get_current_user_as_doctor,
    ):
        doctor_id = fake_get_current_user_as_doctor.doctor.id
        now = datetime.now(UTC).replace(tzinfo=None)

        spec = Specialty(
            name="Dermatology",
            description="Skin care",
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(spec)
        await get_test_session.commit()
        await get_test_session.refresh(spec)

        payload = {"specialty_ids": [spec.id]}
        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 200

        query = (
            select(Doctor)
            .where(Doctor.id == doctor_id)
            .options(selectinload(Doctor.specialties))
        )
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert len(doctor_in_db.specialties) == 1
        assert doctor_in_db.specialties[0].id == spec.id

    async def test_update_doctor_specialties_clear(
        self,
        ac,
        get_test_session,
        fake_get_current_user_as_doctor,
    ):
        doctor_id = fake_get_current_user_as_doctor.doctor.id
        payload = {"specialty_ids": []}

        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 200

        query = (
            select(Doctor)
            .where(Doctor.id == doctor_id)
            .options(selectinload(Doctor.specialties))
        )
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert doctor_in_db.specialties == []

    async def test_update_doctor_nonexistent_specialties_error(
        self,
        ac,
        fake_get_current_user_as_doctor,
    ):
        payload = {"specialty_ids": [9999]}
        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 404

    async def test_update_doctor_empty_body(
        self,
        ac,
        fake_get_current_user_as_doctor,
    ):
        current_doctor = fake_get_current_user_as_doctor.doctor
        response = await ac.patch("/doctors/me", json={})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == current_doctor.id
        assert data["education"] == current_doctor.education

    async def test_update_doctor_pending_status_forbidden(
        self,
        ac,
        pending_doctor_user,
    ):
        payload = {"bio": "Trying to update"}
        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 403

    async def test_update_doctor_unauthorized(
        self,
        ac,
    ):
        payload = {"bio": "No authorization"}
        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 401


class TestDoctorDelete:
    async def test_delete_doctor_account_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        fake_get_current_user_as_doctor,
    ):
        user_id = fake_get_current_user_as_doctor.id
        doctor_id = fake_get_current_user_as_doctor.doctor.id

        cache_key = fake_get_redis.build_key("doctors", "items", doctor_id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        payload = {"password": "test_hashed_password"}
        response = await ac.request("DELETE", "/doctors/me", json=payload)
        assert response.status_code == 204

        query_doc = select(Doctor).where(Doctor.id == doctor_id)
        result_doc = await get_test_session.execute(query_doc)
        assert result_doc.scalar_one_or_none() is None

        query_user = select(User).where(User.id == user_id)
        result_user = await get_test_session.execute(query_user)
        user_in_db = result_user.scalar_one()
        assert user_in_db.role == UserRole.CLIENT

        assert await fake_get_redis.getc(cache_key) is None

    async def test_delete_doctor_account_incorrect_password(
        self,
        ac,
        fake_get_current_user_as_doctor,
    ):
        payload = {"password": "wrong_password"}
        response = await ac.request("DELETE", "/doctors/me", json=payload)
        assert response.status_code == 400

    async def test_delete_doctor_account_pending_forbidden(
        self,
        ac,
        pending_doctor_user,
    ):
        payload = {"password": "fake_password_secret"}
        response = await ac.request("DELETE", "/doctors/me", json=payload)
        assert response.status_code == 403

    async def test_delete_doctor_account_unauthorized(
        self,
        ac,
    ):
        payload = {"password": "test_password"}
        response = await ac.request("DELETE", "/doctors/me", json=payload)
        assert response.status_code == 401


class TestDoctorAvatarDelete:
    async def test_delete_doctor_avatar_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        fake_get_current_user_as_doctor,
    ):
        doctor_id = fake_get_current_user_as_doctor.doctor.id
        old_avatar_url = fake_get_current_user_as_doctor.doctor.avatar_url
        assert old_avatar_url is not None

        cache_key = fake_get_redis.build_key("doctors", "items", doctor_id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        with patch("src.modules.doctors.service.delete_image", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = None

            response = await ac.delete("/doctors/avatar")
            assert response.status_code == 204

            mock_delete.assert_awaited_once_with(old_avatar_url)

        query = select(Doctor).where(Doctor.id == doctor_id)
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()

        assert doctor_in_db.avatar_url is None
        assert await fake_get_redis.getc(cache_key) is None

    async def test_delete_doctor_avatar_when_no_avatar(
        self,
        ac,
        get_test_session,
        fake_get_current_user_as_doctor,
    ):
        doctor = fake_get_current_user_as_doctor.doctor
        doctor.avatar_url = None

        with patch("src.modules.doctors.service.delete_image", new_callable=AsyncMock) as mock_delete:
            response = await ac.delete("/doctors/avatar")
            assert response.status_code == 204
            mock_delete.assert_not_called()

    async def test_delete_doctor_avatar_unauthorized(
        self,
        ac,
    ):
        response = await ac.delete("/doctors/avatar")
        assert response.status_code == 401