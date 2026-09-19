import io
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.common.enums import CacheTTL, ModerationStatus, UserRole
from src.modules.doctors.models import Doctor
from src.modules.users.models import User
from tests.service import create_test_image


class TestRegisterDoctor:
    async def test_register_doctor_success(
        self, ac, get_test_session, fake_get_current_user
    ):
        doctor_data = {
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Board-certified cardiologist specializing in preventive cardiology.",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 201
        data = response.json()

        query = select(Doctor).where(Doctor.id == data["id"])
        result = await get_test_session.execute(query)
        doctor = result.scalar_one_or_none()

        assert doctor is not None
        assert doctor.specialties == []
        assert doctor.education == doctor_data["education"]
        assert doctor.status == ModerationStatus.PENDING

    async def test_register_doctor_already_exists(
        self, ac, fake_get_current_user_as_doctor
    ):
        doctor_data = {
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Specialist bio.",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 409
        assert response.json()["detail"] == "Doctor profile already exists"

    async def test_register_doctor_specialties_not_found(
        self, ac, fake_get_current_user
    ):
        doctor_data = {
            "specialty_ids": [9999, 8888],
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Specialist bio.",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "One or more specialties not found"

    async def test_register_doctor_with_specialties(
        self, ac, get_test_session, fake_get_current_user, seed_specialties
    ):
        spec1, spec2 = seed_specialties
        doctor_data = {
            "specialty_ids": [spec1.id, spec2.id],
            "education": "Harvard Medical School, MD (2012)",
            "degree": "Doctor of Medicine (MD)",
            "experience_years": 14,
            "bio": "Board-certified cardiologist.",
            "clinic": "Boston Heart & Vascular Center",
        }
        response = await ac.post("/doctors/register", json=doctor_data)
        assert response.status_code == 201
        data = response.json()

        query = select(Doctor).where(Doctor.id == data["id"])
        result = await get_test_session.execute(query)
        doctor = result.scalar_one_or_none()

        specialty_ids = [s.id for s in doctor.specialties]
        assert sorted(specialty_ids) == sorted([spec1.id, spec2.id])

    async def test_register_doctor_invalidates_cache(
        self, ac, fake_get_redis, fake_get_current_user
    ):
        cache_key = fake_get_redis.build_key("doctors", "list", "default")
        await fake_get_redis.setc(cache_key, [{"fake": "list"}], CacheTTL.FAST)
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

    async def test_upload_doctor_avatar_invalid_extension(
        self, ac, fake_get_current_user_as_doctor
    ):
        text_file = io.BytesIO(b"not an image content")
        files = {"image": ("file.txt", text_file, "text/plain")}
        response = await ac.post("/doctors/avatar", files=files)
        assert response.status_code == 415

    async def test_upload_doctor_avatar_corrupted_image_data(
        self, ac, fake_get_current_user_as_doctor
    ):
        corrupted_data = io.BytesIO(b"fake image bytes")
        files = {"image": ("avatar.png", corrupted_data, "image/png")}
        response = await ac.post("/doctors/avatar", files=files)
        assert response.status_code == 415


class TestGetDoctorsByFilters:
    @pytest.fixture
    async def seed_doctors(self, get_test_session, doctor_factory, seed_specialties):
        spec_cardio, spec_neuro = seed_specialties

        doc1 = await doctor_factory(
            education="Medical School 1",
            experience_years=10,
            min_price=100,
            clinic="Clinic 1",
            rating_avg=4.8,
            reviews_count=15,
            status=ModerationStatus.APPROVED,
            specialties=[spec_cardio],
        )
        doc2 = await doctor_factory(
            education="Medical School 2",
            experience_years=3,
            min_price=250,
            clinic="Clinic 2",
            rating_avg=4.0,
            reviews_count=5,
            status=ModerationStatus.APPROVED,
            specialties=[spec_neuro],
        )
        doc3 = await doctor_factory(
            education="Medical School 3",
            experience_years=7,
            min_price=150,
            clinic="Clinic 3",
            rating_avg=4.5,
            reviews_count=8,
            status=ModerationStatus.PENDING,
            specialties=[spec_cardio, spec_neuro],
        )
        await get_test_session.commit()

        return {
            "doctors": [doc1, doc2, doc3],
            "specialties": [spec_cardio, spec_neuro],
        }

    async def test_get_doctors_default_list(self, ac, fake_get_redis, seed_doctors):
        response = await ac.get("/doctors/")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        cache_key = fake_get_redis.build_key("doctors", "list", "default")
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert cached_data["total"] == 2

    async def test_get_doctors_returns_cached_data(self, ac, fake_get_redis):
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

    async def test_filter_by_specialty(self, ac, seed_doctors):
        spec_neuro = seed_doctors["specialties"][1]
        response = await ac.get(f"/doctors/?specialty_ids={spec_neuro.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["clinic"] == "Clinic 2"

    async def test_filter_by_experience_years(self, ac, seed_doctors):
        response = await ac.get("/doctors/?experience_years=5")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["experience_years"] == 10

    async def test_filter_by_max_price(self, ac, seed_doctors):
        response = await ac.get("/doctors/?max_price=200")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["min_price"] == 100

    async def test_filter_by_rating_avg(self, ac, seed_doctors):
        response = await ac.get("/doctors/?rating_avg=4.5")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["rating_avg"] == 4.8

    async def test_filter_by_status_as_admin(
        self, ac, seed_doctors, fake_optional_admin_user
    ):
        response = await ac.get("/doctors/?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["clinic"] == "Clinic 3"

    async def test_filter_by_status_ignored_for_guest(self, ac, seed_doctors):
        response = await ac.get("/doctors/?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert all(
            item["status"] == ModerationStatus.APPROVED for item in data["items"]
        )


class TestDoctorProfile:
    async def test_get_my_doctor_profile_success(
        self, ac, fake_get_current_user_as_doctor
    ):
        response = await ac.get("/doctors/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == fake_get_current_user_as_doctor.doctor.id
        assert data["clinic"] == fake_get_current_user_as_doctor.doctor.clinic

    async def test_get_my_doctor_profile_not_a_doctor(self, ac, fake_get_current_user):
        response = await ac.get("/doctors/me")
        assert response.status_code == 404
        assert response.json()["detail"] == "Doctor not found"


class TestDoctorById:
    @pytest.fixture
    async def persisted_doctor(
        self, get_test_session, doctor_factory, seed_specialties
    ):
        doc = await doctor_factory(
            education="Harvard Medical School",
            experience_years=12,
            bio="Experienced cardiologist.",
            min_price=200,
            clinic="Cardio Care Clinic",
            rating_avg=4.9,
            reviews_count=35,
            status=ModerationStatus.APPROVED,
            specialties=[seed_specialties[0]],
        )
        await get_test_session.commit()
        await get_test_session.refresh(doc)
        return doc

    async def test_get_doctor_by_id_success(self, ac, persisted_doctor, fake_get_redis):
        response = await ac.get(f"/doctors/{persisted_doctor.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == persisted_doctor.id
        assert data["clinic"] == persisted_doctor.clinic
        assert len(data["specialties"]) == 1

        cache_key = fake_get_redis.build_key("doctors", "items", persisted_doctor.id)
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert cached_data["id"] == persisted_doctor.id

    async def test_get_doctor_by_id_returns_cached_data(self, ac, fake_get_redis):
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

    async def test_get_doctor_by_id_not_found(self, ac):
        response = await ac.get("/doctors/99999")
        assert response.status_code == 404

    async def test_get_rejected_doctor_hides_rejection_reason_for_guest(
        self, ac, get_test_session, doctor_factory
    ):
        rejected_doc = await doctor_factory(
            status=ModerationStatus.REJECTED,
            rejection_reason="Incomplete documents",
        )
        await get_test_session.commit()

        guest_response = await ac.get(f"/doctors/{rejected_doc.id}")
        assert guest_response.status_code == 404

    async def test_get_rejected_doctor_shows_rejection_reason_for_admin(
        self, ac, get_test_session, doctor_factory, fake_optional_admin_user
    ):
        rejected_doc = await doctor_factory(
            status=ModerationStatus.REJECTED,
            rejection_reason="Incomplete documents",
        )
        await get_test_session.commit()

        response = await ac.get(f"/doctors/{rejected_doc.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["rejection_reason"] == "Incomplete documents"


class TestDoctorModeration:
    @pytest.fixture
    async def pending_doctor(self, get_test_session, doctor_factory):
        doc = await doctor_factory(
            education="Medical Academy",
            clinic="Pending Clinic",
            status=ModerationStatus.PENDING,
        )
        await get_test_session.commit()
        await get_test_session.refresh(doc)
        return doc

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
        assert await fake_get_redis.getc(cache_key) is None

    async def test_approve_doctor_unauthorized(self, ac, pending_doctor):
        response = await ac.patch(f"/doctors/{pending_doctor.id}/approve")
        assert response.status_code == 401

    async def test_approve_doctor_not_found(self, ac, fake_get_admin_user):
        response = await ac.patch("/doctors/99999/approve")
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

        payload = {"rejection_reason": "Incomplete medical license documents"}
        response = await ac.patch(f"/doctors/{pending_doctor.id}/reject", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == pending_doctor.id
        assert data["status"] == ModerationStatus.REJECTED
        assert data["rejection_reason"] == payload["rejection_reason"]

        query_doc = select(Doctor).where(Doctor.id == pending_doctor.id)
        result_doc = await get_test_session.execute(query_doc)
        doctor_in_db = result_doc.scalar_one()
        assert doctor_in_db.status == ModerationStatus.REJECTED

        query_user = select(User).where(User.id == pending_doctor.user_id)
        result_user = await get_test_session.execute(query_user)
        user_in_db = result_user.scalar_one()
        assert user_in_db.role == UserRole.CLIENT

        assert await fake_get_redis.getc(cache_key) is None

    async def test_reject_doctor_validation_error(
        self, ac, fake_get_admin_user, pending_doctor
    ):
        response = await ac.patch(f"/doctors/{pending_doctor.id}/reject", json={})
        assert response.status_code == 422

    async def test_reject_doctor_unauthorized(self, ac, pending_doctor):
        payload = {"rejection_reason": "No access"}
        response = await ac.patch(f"/doctors/{pending_doctor.id}/reject", json=payload)
        assert response.status_code == 401


class TestDoctorUpdate:
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

        query = select(Doctor).where(Doctor.id == doctor_id)
        result = await get_test_session.execute(query)
        doctor_in_db = result.scalar_one()
        assert doctor_in_db.education == payload["education"]
        assert await fake_get_redis.getc(cache_key) is None

    async def test_update_doctor_specialties_replace(
        self,
        ac,
        get_test_session,
        fake_get_current_user_as_doctor,
        seed_specialties,
    ):
        doctor_id = fake_get_current_user_as_doctor.doctor.id
        target_spec = seed_specialties[0]

        payload = {"specialty_ids": [target_spec.id]}
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
        assert doctor_in_db.specialties[0].id == target_spec.id

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
        self, ac, fake_get_current_user_as_doctor
    ):
        payload = {"specialty_ids": [99999]}
        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 404

    async def test_update_doctor_empty_body(self, ac, fake_get_current_user_as_doctor):
        current_doctor = fake_get_current_user_as_doctor.doctor
        response = await ac.patch("/doctors/me", json={})
        assert response.status_code == 200
        assert response.json()["id"] == current_doctor.id

    async def test_update_doctor_pending_status_forbidden(self, ac, pending_doctor):
        payload = {"bio": "Trying to update"}
        response = await ac.patch("/doctors/me", json=payload)
        assert response.status_code == 403

    async def test_update_doctor_unauthorized(self, ac):
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
        self, ac, fake_get_current_user_as_doctor
    ):
        payload = {"password": "wrong_password"}
        response = await ac.request("DELETE", "/doctors/me", json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == "Incorrect password"

    async def test_delete_doctor_account_pending_forbidden(self, ac, pending_doctor):
        payload = {"password": "fake_password_secret"}
        response = await ac.request("DELETE", "/doctors/me", json=payload)
        assert response.status_code == 403

    async def test_delete_doctor_account_unauthorized(self, ac):
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

        with patch(
            "src.modules.doctors.service.delete_image", new_callable=AsyncMock
        ) as mock_delete:
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
        self, ac, fake_get_current_user_as_doctor
    ):
        doctor = fake_get_current_user_as_doctor.doctor
        doctor.avatar_url = None

        with patch(
            "src.modules.doctors.service.delete_image", new_callable=AsyncMock
        ) as mock_delete:
            response = await ac.delete("/doctors/avatar")
            assert response.status_code == 204
            mock_delete.assert_not_called()

    async def test_delete_doctor_avatar_unauthorized(self, ac):
        response = await ac.delete("/doctors/avatar")
        assert response.status_code == 401
