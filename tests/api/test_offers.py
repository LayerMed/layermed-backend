from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from main import app
from src.common.enums import CacheTTL, ModerationStatus, OfferFormat, UserRole
from src.core.dependencies import get_current_doctor
from src.core.security import hash_pwd
from src.modules.cities.models import City
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.models import Offer
from src.modules.users.models import User
from tests.service import create_test_image


class TestCreateOffer:
    async def test_create_offer_success(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        seed_city,
    ):
        payload = {
            "city_id": seed_city.id,
            "title": "Initial Cardiology Consultation",
            "description": "Comprehensive cardiac check-up including ECG review.",
            "cost": 150,
            "offer_format": OfferFormat.CLINIC.value,
        }

        response = await ac.post("/offers/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["id"] is not None
        assert data["doctor_id"] == fake_get_current_doctor.id
        assert data["city_id"] == seed_city.id
        assert data["title"] == payload["title"]
        assert data["status"] == ModerationStatus.PENDING.value
        assert data["images"] == []

        query = select(Offer).where(Offer.id == data["id"])
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one_or_none()
        assert db_offer is not None
        assert db_offer.doctor_id == fake_get_current_doctor.id
        assert db_offer.status == ModerationStatus.PENDING

    async def test_create_offer_invalidates_cache(
        self,
        ac,
        fake_get_redis,
        fake_get_current_doctor,
        seed_city,
    ):
        cache_key = fake_get_redis.build_key("offers", "list", "default")
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)
        assert await fake_get_redis.getc(cache_key) is not None

        payload = {
            "city_id": seed_city.id,
            "title": "Cache Invalidation Check",
            "description": "Checking if creating an offer flushes redis cache.",
            "cost": 100,
            "offer_format": OfferFormat.ONLINE.value,
        }

        response = await ac.post("/offers/", json=payload)
        assert response.status_code == 201
        assert await fake_get_redis.getc(cache_key) is None

    async def test_create_offer_validation_error(
        self,
        ac,
        fake_get_current_doctor,
        seed_city,
    ):
        payload = {
            "city_id": seed_city.id,
            "title": "A",
            "description": "Short",
            "cost": 0,
            "offer_format": OfferFormat.CLINIC.value,
        }
        response = await ac.post("/offers/", json=payload)
        assert response.status_code == 422

    async def test_create_offer_unauthorized(
        self,
        ac,
        seed_city,
    ):
        payload = {
            "city_id": seed_city.id,
            "title": "Unauthorized Offer",
            "description": "Should fail because no doctor is injected.",
            "cost": 100,
            "offer_format": OfferFormat.ONLINE.value,
        }
        response = await ac.post("/offers/", json=payload)
        assert response.status_code == 401

    async def test_upload_offer_images_success(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        seed_city,
    ):
        offer = Offer(
            doctor_id=fake_get_current_doctor.id,
            city_id=seed_city.id,
            title="Consultation for photos",
            description="Consultation description with photos attached.",
            cost=120,
            offer_format=OfferFormat.CLINIC,
            status=ModerationStatus.APPROVED,
            images=[],
        )
        get_test_session.add(offer)
        await get_test_session.commit()
        await get_test_session.refresh(offer)

        mocked_keys = ["offers/img_1.jpg", "offers/img_2.jpg"]
        files = [
            ("images", ("img1.jpg", create_test_image(), "image/jpeg")),
            ("images", ("img2.jpg", create_test_image(), "image/jpeg")),
        ]

        with patch(
            "src.modules.offers.service.save_and_upload_image",
            new_callable=AsyncMock,
            side_effect=mocked_keys,
        ) as mock_upload:
            response = await ac.post(f"/offers/{offer.id}/images", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data == mocked_keys
        assert mock_upload.await_count == 2

        query = select(Offer).where(Offer.id == offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()
        assert db_offer.images == mocked_keys

    async def test_upload_offer_images_exceeds_limit(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        seed_city,
    ):
        existing_images = [f"offers/img_{i}.jpg" for i in range(9)]
        offer = Offer(
            doctor_id=fake_get_current_doctor.id,
            city_id=seed_city.id,
            title="Almost Full Offer",
            description="Offer containing 9 images already.",
            cost=120,
            offer_format=OfferFormat.CLINIC,
            status=ModerationStatus.APPROVED,
            images=existing_images,
        )
        get_test_session.add(offer)
        await get_test_session.commit()
        await get_test_session.refresh(offer)

        files = [
            ("images", ("img1.jpg", create_test_image(), "image/jpeg")),
            ("images", ("img2.jpg", create_test_image(), "image/jpeg")),
        ]
        response = await ac.post(f"/offers/{offer.id}/images", files=files)
        assert response.status_code == 400
        assert (
            response.json()["detail"] == "Images count exceeds the limit of 10 pieces"
        )

    async def test_upload_offer_images_access_denied(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        seed_city,
    ):
        now = datetime.now(UTC).replace(tzinfo=None)

        other_user = User(
            name="Other Doctor",
            email="other_doctor_images@test.com",
            password=hash_pwd("test_hashed_password"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(other_user)
        await get_test_session.flush()

        other_doctor = Doctor(
            user_id=other_user.id,
            education="Second Medical University",
            degree="MD",
            experience_years=6,
            bio="Surgeon bio",
            clinic="Second Clinic",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(other_doctor)
        await get_test_session.flush()

        offer = Offer(
            doctor_id=other_doctor.id,
            city_id=seed_city.id,
            title="Foreign Doctor Offer",
            description="Belongs to someone else.",
            cost=200,
            offer_format=OfferFormat.CLINIC,
            status=ModerationStatus.APPROVED,
            images=[],
        )
        get_test_session.add(offer)
        await get_test_session.commit()
        await get_test_session.refresh(offer)

        files = [("images", ("img1.jpg", create_test_image(), "image/jpeg"))]
        response = await ac.post(f"/offers/{offer.id}/images", files=files)
        assert response.status_code == 403
        assert (
            response.json()["detail"]
            == "You do not have the rights to access this offer."
        )

    async def test_upload_offer_images_not_found(
        self,
        ac,
        fake_get_current_doctor,
    ):
        files = [("images", ("img1.jpg", create_test_image(), "image/jpeg"))]
        response = await ac.post("/offers/99999/images", files=files)
        assert response.status_code == 404
        assert response.json()["detail"] == "Offer not found"


class TestReadOffers:
    @pytest.fixture
    async def seed_offers_setup(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        city1 = City(name="City One")
        city2 = City(name="City Two")
        get_test_session.add_all([city1, city2])
        await get_test_session.flush()

        user1 = User(
            name="Doctor Alpha",
            email="doc_alpha@test.com",
            password=hash_pwd("pwd1"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            name="Doctor Beta",
            email="doc_beta@test.com",
            password=hash_pwd("pwd2"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([user1, user2])
        await get_test_session.flush()

        doc1 = Doctor(
            user_id=user1.id,
            education="Med School 1",
            experience_years=12,
            bio="Bio 1",
            min_price=100,
            clinic="Clinic 1",
            rating_avg=4.9,
            reviews_count=20,
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        doc2 = Doctor(
            user_id=user2.id,
            education="Med School 2",
            experience_years=3,
            bio="Bio 2",
            min_price=50,
            clinic="Clinic 2",
            rating_avg=3.8,
            reviews_count=5,
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([doc1, doc2])
        await get_test_session.flush()

        offer1 = Offer(
            doctor_id=doc1.id,
            city_id=city1.id,
            title="Cardio Complete Checkup",
            description="Detailed heart examination",
            cost=200,
            status=ModerationStatus.APPROVED,
            offer_format=OfferFormat.CLINIC,
            images=[],
            created_at=now,
            updated_at=now,
        )
        offer2 = Offer(
            doctor_id=doc1.id,
            city_id=city2.id,
            title="Online Therapy",
            description="Remote medical help",
            cost=80,
            status=ModerationStatus.APPROVED,
            offer_format=OfferFormat.ONLINE,
            images=[],
            created_at=now,
            updated_at=now,
        )
        offer3 = Offer(
            doctor_id=doc2.id,
            city_id=city1.id,
            title="Pending Checkup",
            description="Waiting for moderation approval",
            cost=120,
            status=ModerationStatus.PENDING,
            offer_format=OfferFormat.CLINIC,
            images=[],
            created_at=now,
            updated_at=now,
        )

        get_test_session.add_all([offer1, offer2, offer3])
        await get_test_session.commit()
        await get_test_session.refresh(offer1)
        await get_test_session.refresh(offer2)
        await get_test_session.refresh(offer3)

        return {
            "cities": [city1, city2],
            "doctors": [doc1, doc2],
            "offers": [offer1, offer2, offer3],
        }

    async def test_get_offers_default_list(
        self,
        ac,
        fake_get_redis,
        seed_offers_setup,
    ):
        response = await ac.get("/offers/")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert all(
            item["status"] == ModerationStatus.APPROVED for item in data["items"]
        )

        cache_key = fake_get_redis.build_key("offers", "list", "default")
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert cached_data["total"] == 2

    async def test_get_offers_returns_cached_data(
        self,
        ac,
        fake_get_redis,
    ):
        cache_key = fake_get_redis.build_key("offers", "list", "default")
        fake_payload = {
            "items": [],
            "limit": 10,
            "offset": 0,
            "total": 0,
        }
        await fake_get_redis.setc(cache_key, fake_payload, CacheTTL.FAST)

        response = await ac.get("/offers/")
        assert response.status_code == 200
        assert response.json() == fake_payload

    async def test_filter_offers_by_city(
        self,
        ac,
        seed_offers_setup,
    ):
        city2 = seed_offers_setup["cities"][1]
        response = await ac.get(f"/offers/?city_id={city2.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["city_id"] == city2.id

    async def test_filter_offers_by_cost(
        self,
        ac,
        seed_offers_setup,
    ):
        response = await ac.get("/offers/?cost=100")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["cost"] == 80

    async def test_filter_offers_by_format(
        self,
        ac,
        seed_offers_setup,
    ):
        response = await ac.get(f"/offers/?offer_format={OfferFormat.ONLINE}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["offer_format"] == OfferFormat.ONLINE

    async def test_filter_offers_by_doctor_attributes(
        self,
        ac,
        seed_offers_setup,
    ):
        response = await ac.get(
            "/offers/?doctor_experience_years=10&doctor_rating_avg=4"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert all(
            item["doctor_id"] == seed_offers_setup["doctors"][0].id
            for item in data["items"]
        )

    async def test_filter_offers_by_status_as_admin(
        self, ac, seed_offers_setup, fake_optional_admin_user
    ):
        response = await ac.get(f"/offers/?status={ModerationStatus.PENDING}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == ModerationStatus.PENDING

    async def test_filter_offers_by_status_ignored_for_guest(
        self,
        ac,
        seed_offers_setup,
    ):
        response = await ac.get(f"/offers/?status={ModerationStatus.PENDING}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert all(
            item["status"] == ModerationStatus.APPROVED for item in data["items"]
        )

    async def test_get_offers_by_doctor_success(
        self,
        ac,
        seed_offers_setup,
    ):
        target_doc = seed_offers_setup["doctors"][0]
        doc_read = DoctorRead.model_validate(target_doc)
        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.get("/offers/doctor")
            assert response.status_code == 200

            data = response.json()
            assert len(data) == 2
            assert all(item["doctor_id"] == target_doc.id for item in data)
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)

    async def test_get_offers_by_doctor_not_found(
        self,
        ac,
        get_test_session,
    ):
        now = datetime.now(UTC).replace(tzinfo=None)
        empty_user = User(
            name="Empty Doctor",
            email="empty_doc@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(empty_user)
        await get_test_session.flush()

        empty_doc = Doctor(
            user_id=empty_user.id,
            education="Med School",
            experience_years=1,
            bio="No offers yet",
            min_price=10,
            clinic="Empty Clinic",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(empty_doc)
        await get_test_session.commit()
        await get_test_session.refresh(empty_doc)

        doc_read = DoctorRead.model_validate(empty_doc)
        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.get("/offers/doctor")
            assert response.status_code == 404
            assert response.json()["detail"] == "Offer not found"
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)

    async def test_get_offer_by_id_success(
        self,
        ac,
        fake_get_redis,
        seed_offers_setup,
    ):
        target_offer = seed_offers_setup["offers"][0]
        response = await ac.get(f"/offers/{target_offer.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_offer.id
        assert data["title"] == target_offer.title

        cache_key = fake_get_redis.build_key("offers", "items", target_offer.id)
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert cached_data["id"] == target_offer.id

    async def test_get_offer_by_id_returns_cached_data(
        self,
        ac,
        fake_get_redis,
    ):
        offer_id = 555
        cache_key = fake_get_redis.build_key("offers", "items", offer_id)
        fake_offer_payload = {
            "id": offer_id,
            "doctor_id": 1,
            "city_id": 1,
            "title": "Cached Offer Title",
            "description": "Cached Offer Description",
            "cost": 150,
            "status": ModerationStatus.APPROVED,
            "offer_format": OfferFormat.CLINIC,
            "rejection_reason": None,
            "images": [],
        }
        await fake_get_redis.setc(cache_key, fake_offer_payload, CacheTTL.SLOW)

        response = await ac.get(f"/offers/{offer_id}")
        assert response.status_code == 200
        assert response.json() == fake_offer_payload

    async def test_get_offer_by_id_not_found(
        self,
        ac,
    ):
        response = await ac.get("/offers/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Offer not found"


class TestUpdateOffers:
    @pytest.fixture
    async def seed_offer_for_update(self, fake_get_current_doctor, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        city = City(name="Update City")
        get_test_session.add(city)
        await get_test_session.flush()

        user = User(
            name="Update Doctor User",
            email="doc_update@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(user)
        await get_test_session.flush()

        doctor = Doctor(
            user_id=user.id,
            education="Update Med",
            experience_years=5,
            bio="Update bio",
            min_price=100,
            clinic="Update Clinic",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.flush()

        offer = Offer(
            doctor_id=fake_get_current_doctor.id,
            city_id=city.id,
            title="Initial Title",
            description="Initial Description",
            cost=150,
            status=ModerationStatus.APPROVED,
            offer_format=OfferFormat.CLINIC,
            images=["offers/old_img_1.jpg", "offers/old_img_2.jpg"],
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(offer)
        await get_test_session.commit()
        await get_test_session.refresh(offer)

        return {"city": city, "doctor": doctor, "offer": offer}

    async def test_update_offer_fields_success(
        self,
        ac,
        fake_get_current_doctor,
        get_test_session,
        fake_get_redis,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        cache_key = fake_get_redis.build_key("offers", "items", target_offer.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.SLOW)

        payload = {
            "title": "Updated Title",
            "cost": 250,
            "offer_format": OfferFormat.ONLINE.value,
        }

        response = await ac.patch(f"/offers/{target_offer.id}", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_offer.id
        assert data["title"] == payload["title"]
        assert data["cost"] == payload["cost"]
        assert data["offer_format"] == payload["offer_format"]
        assert data["status"] == ModerationStatus.PENDING.value

        query = select(Offer).where(Offer.id == target_offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()

        assert db_offer.title == payload["title"]
        assert db_offer.cost == payload["cost"]
        assert db_offer.status == ModerationStatus.PENDING
        assert await fake_get_redis.getc(cache_key) is None

    async def test_update_offer_removes_deleted_images_from_s3(
        self,
        ac,
        fake_get_current_doctor,
        get_test_session,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        payload = {
            "images": ["offers/old_img_1.jpg"],
        }

        with patch(
            "src.modules.offers.service.delete_image",
            new_callable=AsyncMock,
        ) as mock_delete_image:
            mock_delete_image.return_value = None
            response = await ac.patch(f"/offers/{target_offer.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["images"] == ["offers/old_img_1.jpg"]

        mock_delete_image.assert_awaited_once_with("offers/old_img_2.jpg")

        query = select(Offer).where(Offer.id == target_offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()
        assert db_offer.images == ["offers/old_img_1.jpg"]

    async def test_update_offer_empty_body(
        self,
        ac,
        fake_get_current_doctor,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        response = await ac.patch(f"/offers/{target_offer.id}", json={})
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_offer.id
        assert data["title"] == target_offer.title

    async def test_update_offer_not_found(
        self,
        ac,
        fake_get_current_doctor,
    ):
        payload = {"title": "Ghost Offer"}
        response = await ac.patch("/offers/99999", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Offer not found"

    async def test_approve_offer_success(
        self,
        ac,
        get_test_session,
        fake_get_admin_user,
        fake_get_redis,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        target_offer.status = ModerationStatus.PENDING
        await get_test_session.commit()

        cache_key = fake_get_redis.build_key("offers", "items", target_offer.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.SLOW)

        response = await ac.patch(f"/offers/{target_offer.id}/approve")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_offer.id
        assert data["status"] == ModerationStatus.APPROVED.value
        assert data["rejection_reason"] is None

        query = select(Offer).where(Offer.id == target_offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()
        assert db_offer.status == ModerationStatus.APPROVED
        assert await fake_get_redis.getc(cache_key) is None

    async def test_approve_offer_unauthorized(
        self,
        ac,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        response = await ac.patch(f"/offers/{target_offer.id}/approve")
        assert response.status_code == 401

    async def test_reject_offer_success(
        self,
        ac,
        get_test_session,
        fake_get_admin_user,
        fake_get_redis,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        cache_key = fake_get_redis.build_key("offers", "items", target_offer.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.SLOW)

        payload = {"rejection_reason": "Inappropriate medical service description"}
        response = await ac.patch(f"/offers/{target_offer.id}/reject", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_offer.id
        assert data["status"] == ModerationStatus.REJECTED.value
        assert data["rejection_reason"] == payload["rejection_reason"]

        query = select(Offer).where(Offer.id == target_offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()
        assert db_offer.status == ModerationStatus.REJECTED
        assert db_offer.rejection_reason == payload["rejection_reason"]
        assert await fake_get_redis.getc(cache_key) is None

    async def test_reject_offer_validation_error(
        self,
        ac,
        fake_get_admin_user,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        response = await ac.patch(f"/offers/{target_offer.id}/reject", json={})
        assert response.status_code == 422

    async def test_reject_offer_unauthorized(
        self,
        ac,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update["offer"]
        payload = {"rejection_reason": "Without token"}
        response = await ac.patch(f"/offers/{target_offer.id}/reject", json=payload)
        assert response.status_code == 401


class TestDeleteOffers:
    @pytest.fixture
    async def seed_offer_for_delete(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        city = City(name="Delete City")
        get_test_session.add(city)
        await get_test_session.flush()

        user1 = User(
            name="Doctor Delete Owner",
            email="doc_del_owner@test.com",
            password=hash_pwd("pwd1"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            name="Doctor Foreign",
            email="doc_foreign@test.com",
            password=hash_pwd("pwd2"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([user1, user2])
        await get_test_session.flush()

        doc1 = Doctor(
            user_id=user1.id,
            education="Delete Med School 1",
            experience_years=8,
            bio="Bio 1",
            min_price=120,
            clinic="Clinic 1",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        doc2 = Doctor(
            user_id=user2.id,
            education="Delete Med School 2",
            experience_years=4,
            bio="Bio 2",
            min_price=90,
            clinic="Clinic 2",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([doc1, doc2])
        await get_test_session.flush()

        offer = Offer(
            doctor_id=doc1.id,
            city_id=city.id,
            title="Offer to Delete",
            description="Offer that should be removed",
            cost=180,
            status=ModerationStatus.APPROVED,
            offer_format=OfferFormat.CLINIC,
            images=[],
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(offer)
        await get_test_session.commit()
        await get_test_session.refresh(offer)

        return {
            "city": city,
            "owner_doctor": doc1,
            "foreign_doctor": doc2,
            "offer": offer,
        }

    async def test_delete_offer_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        seed_offer_for_delete,
    ):
        target_offer = seed_offer_for_delete["offer"]
        owner_doc = seed_offer_for_delete["owner_doctor"]
        doc_read = DoctorRead.model_validate(owner_doc)

        cache_key = fake_get_redis.build_key("offers", "items", target_offer.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.SLOW)

        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.delete(f"/offers/{target_offer.id}")
            assert response.status_code == 204

            query = select(Offer).where(Offer.id == target_offer.id)
            result = await get_test_session.execute(query)
            db_offer = result.scalar_one_or_none()
            assert db_offer is None

            assert await fake_get_redis.getc(cache_key) is None
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)

    async def test_delete_offer_access_denied(
        self,
        ac,
        get_test_session,
        seed_offer_for_delete,
    ):
        target_offer = seed_offer_for_delete["offer"]
        foreign_doc = seed_offer_for_delete["foreign_doctor"]
        doc_read = DoctorRead.model_validate(foreign_doc)

        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.delete(f"/offers/{target_offer.id}")
            assert response.status_code == 403
            assert (
                response.json()["detail"]
                == "You do not have the rights to access this offer."
            )

            query = select(Offer).where(Offer.id == target_offer.id)
            result = await get_test_session.execute(query)
            db_offer = result.scalar_one_or_none()
            assert db_offer is not None
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)

    async def test_delete_offer_not_found(
        self,
        ac,
        seed_offer_for_delete,
    ):
        owner_doc = seed_offer_for_delete["owner_doctor"]
        doc_read = DoctorRead.model_validate(owner_doc)

        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.delete("/offers/99999")
            assert response.status_code == 404
            assert response.json()["detail"] == "Offer not found"
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)

    async def test_delete_offer_unauthorized(
        self,
        ac,
        seed_offer_for_delete,
    ):
        target_offer = seed_offer_for_delete["offer"]
        response = await ac.delete(f"/offers/{target_offer.id}")
        assert response.status_code == 401
