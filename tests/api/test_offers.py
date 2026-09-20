from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.common.enums import CacheTTL, ModerationStatus, OfferFormat
from src.modules.offers.models import Offer
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


class TestOfferImages:
    async def test_upload_offer_images_success(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        offer_factory,
    ):
        offer = await offer_factory(
            doctor_id=fake_get_current_doctor.id,
            images=[],
        )
        await get_test_session.commit()

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
        offer_factory,
    ):
        existing_images = [f"offers/img_{i}.jpg" for i in range(9)]
        offer = await offer_factory(
            doctor_id=fake_get_current_doctor.id,
            images=existing_images,
        )
        await get_test_session.commit()

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
        doctor_factory,
        offer_factory,
    ):
        other_doctor = await doctor_factory()
        offer = await offer_factory(doctor_id=other_doctor.id)
        await get_test_session.commit()

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

    async def test_delete_offer_image_success(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        offer_factory,
    ):
        target_image = "offers/target_delete.jpg"
        offer = await offer_factory(
            doctor_id=fake_get_current_doctor.id,
            images=["offers/keep.jpg", target_image],
        )
        await get_test_session.commit()

        with patch(
            "src.modules.offers.service.delete_image", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = True
            response = await ac.delete(f"/offers/{offer.id}/images/{target_image}")

        assert response.status_code == 204
        mock_delete.assert_awaited_once_with(target_image)

        query = select(Offer).where(Offer.id == offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()
        assert db_offer.images == ["offers/keep.jpg"]

    async def test_delete_offer_image_not_found_in_offer(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        offer_factory,
    ):
        offer = await offer_factory(
            doctor_id=fake_get_current_doctor.id,
            images=["offers/existing.jpg"],
        )
        await get_test_session.commit()

        response = await ac.delete(f"/offers/{offer.id}/images/offers/non_existent.jpg")
        assert response.status_code == 404
        assert response.json()["detail"] == "Image not found in this offer"


class TestReadOffers:
    @pytest.fixture
    async def seed_offers_setup(
        self, get_test_session, doctor_factory, offer_factory, seed_city
    ):
        doc1 = await doctor_factory(
            education="Med School 1",
            experience_years=12,
            min_price=100,
            rating_avg=4.9,
        )
        doc2 = await doctor_factory(
            education="Med School 2",
            experience_years=3,
            min_price=50,
            rating_avg=3.8,
        )

        offer1 = await offer_factory(
            doctor=doc1,
            city=seed_city,
            title="Cardio Complete Checkup",
            cost=200,
            status=ModerationStatus.APPROVED,
            offer_format=OfferFormat.CLINIC,
        )
        offer2 = await offer_factory(
            doctor=doc1,
            title="Online Therapy",
            cost=80,
            status=ModerationStatus.APPROVED,
            offer_format=OfferFormat.ONLINE,
        )
        offer3 = await offer_factory(
            doctor=doc2,
            city=seed_city,
            title="Pending Checkup",
            cost=120,
            status=ModerationStatus.PENDING,
            offer_format=OfferFormat.CLINIC,
        )
        await get_test_session.commit()

        return {
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
        target_city_id = seed_offers_setup["offers"][0].city_id
        response = await ac.get(f"/offers/?city_id={target_city_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 1
        assert all(item["city_id"] == target_city_id for item in data["items"])

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
        fake_get_current_doctor,
        offer_factory,
        get_test_session,
    ):
        offer = await offer_factory(doctor_id=fake_get_current_doctor.id)
        await get_test_session.commit()

        response = await ac.get("/offers/doctor")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        assert all(item["doctor_id"] == fake_get_current_doctor.id for item in data)

    async def test_get_offers_by_doctor_not_found(
        self,
        ac,
        fake_get_current_doctor,
    ):
        response = await ac.get("/offers/doctor")
        assert response.status_code == 404
        assert response.json()["detail"] == "Offer not found"

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
    async def seed_offer_for_update(
        self, fake_get_current_doctor, offer_factory, get_test_session
    ):
        offer = await offer_factory(
            doctor_id=fake_get_current_doctor.id,
            title="Initial Title",
            cost=150,
            status=ModerationStatus.APPROVED,
            images=["offers/old_img_1.jpg", "offers/old_img_2.jpg"],
        )
        await get_test_session.commit()
        await get_test_session.refresh(offer)
        return offer

    async def test_update_offer_fields_success(
        self,
        ac,
        fake_get_current_doctor,
        get_test_session,
        fake_get_redis,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update
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
        assert data["status"] == ModerationStatus.PENDING.value

        query = select(Offer).where(Offer.id == target_offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()

        assert db_offer.title == payload["title"]
        assert db_offer.status == ModerationStatus.PENDING
        assert await fake_get_redis.getc(cache_key) is None

    async def test_update_offer_empty_body(
        self,
        ac,
        fake_get_current_doctor,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update
        response = await ac.patch(f"/offers/{target_offer.id}", json={})
        assert response.status_code == 200
        assert response.json()["id"] == target_offer.id

    async def test_update_offer_not_found(
        self,
        ac,
        fake_get_current_doctor,
    ):
        response = await ac.patch("/offers/99999", json={"title": "Ghost Offer"})
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
        target_offer = seed_offer_for_update
        target_offer.status = ModerationStatus.PENDING
        await get_test_session.commit()

        cache_key = fake_get_redis.build_key("offers", "items", target_offer.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.SLOW)

        response = await ac.patch(f"/offers/{target_offer.id}/approve")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_offer.id
        assert data["status"] == ModerationStatus.APPROVED.value

        query = select(Offer).where(Offer.id == target_offer.id)
        result = await get_test_session.execute(query)
        db_offer = result.scalar_one()
        assert db_offer.status == ModerationStatus.APPROVED
        assert await fake_get_redis.getc(cache_key) is None

    async def test_approve_offer_unauthorized(self, ac):
        response = await ac.patch("/offers/1/approve")
        assert response.status_code == 401

    async def test_reject_offer_success(
        self,
        ac,
        get_test_session,
        fake_get_admin_user,
        fake_get_redis,
        seed_offer_for_update,
    ):
        target_offer = seed_offer_for_update
        payload = {"rejection_reason": "Inappropriate medical service description"}
        response = await ac.patch(f"/offers/{target_offer.id}/reject", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_offer.id
        assert data["status"] == ModerationStatus.REJECTED.value
        assert data["rejection_reason"] == payload["rejection_reason"]


class TestDeleteOffers:
    async def test_delete_offer_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        fake_get_current_doctor,
        offer_factory,
    ):
        target_offer = await offer_factory(doctor_id=fake_get_current_doctor.id)
        await get_test_session.commit()

        cache_key = fake_get_redis.build_key("offers", "items", target_offer.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.SLOW)

        response = await ac.delete(f"/offers/{target_offer.id}")
        assert response.status_code == 204

        query = select(Offer).where(Offer.id == target_offer.id)
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is None
        assert await fake_get_redis.getc(cache_key) is None

    async def test_delete_offer_access_denied(
        self,
        ac,
        get_test_session,
        fake_get_current_doctor,
        doctor_factory,
        offer_factory,
    ):
        other_doctor = await doctor_factory()
        target_offer = await offer_factory(doctor_id=other_doctor.id)
        await get_test_session.commit()

        response = await ac.delete(f"/offers/{target_offer.id}")
        assert response.status_code == 403
        assert (
            response.json()["detail"]
            == "You do not have the rights to access this offer."
        )

    async def test_delete_offer_not_found(
        self,
        ac,
        fake_get_current_doctor,
    ):
        response = await ac.delete("/offers/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Offer not found"

    async def test_delete_offer_unauthorized(
        self,
        ac,
        offer_factory,
        get_test_session,
    ):
        offer = await offer_factory()
        await get_test_session.commit()

        response = await ac.delete(f"/offers/{offer.id}")
        assert response.status_code == 401
