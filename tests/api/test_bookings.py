from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.common.enums import (
    BookingStatus,
    CacheTTL,
    ModerationStatus,
    UserRole,
)
from src.modules.bookings.models import Booking


@pytest.fixture
async def seed_offer(offer_factory, get_test_session):
    offer = await offer_factory(status=ModerationStatus.APPROVED)
    await get_test_session.commit()
    await get_test_session.refresh(offer)
    return offer


class TestCreateBooking:
    @pytest.fixture
    async def seed_approved_offer(self, offer_factory, get_test_session):
        offer = await offer_factory(status=ModerationStatus.APPROVED)
        await get_test_session.commit()
        await get_test_session.refresh(offer)
        return offer

    @pytest.fixture
    async def seed_pending_offer(self, offer_factory, get_test_session):
        offer = await offer_factory(status=ModerationStatus.PENDING)
        await get_test_session.commit()
        await get_test_session.refresh(offer)
        return offer

    async def test_create_booking_success(
        self,
        ac,
        get_test_session,
        fake_get_current_user,
        seed_approved_offer,
    ):
        appointment_time = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        payload = {
            "offer_id": seed_approved_offer.id,
            "appointment_time": appointment_time,
        }

        response = await ac.post("/bookings/create", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["user_id"] == fake_get_current_user.id
        assert data["offer_id"] == seed_approved_offer.id
        assert data["status"] == BookingStatus.PENDING
        assert "id" in data

        query = select(Booking).where(Booking.id == data["id"])
        result = await get_test_session.execute(query)
        booking = result.scalar_one_or_none()

        assert booking is not None
        assert booking.user_id == fake_get_current_user.id
        assert booking.offer_id == seed_approved_offer.id
        assert booking.status == BookingStatus.PENDING

    async def test_create_booking_invalidates_user_cache(
        self,
        ac,
        fake_get_current_user,
        fake_get_redis,
        seed_approved_offer,
    ):
        cache_key = fake_get_redis.build_key(
            "bookings", "user", fake_get_current_user.id
        )
        await fake_get_redis.setc(cache_key, [{"fake": "booking"}], CacheTTL.FAST)
        assert await fake_get_redis.getc(cache_key) is not None

        appointment_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        payload = {
            "offer_id": seed_approved_offer.id,
            "appointment_time": appointment_time,
        }

        response = await ac.post("/bookings/create", json=payload)
        assert response.status_code == 201
        assert await fake_get_redis.getc(cache_key) is None

    async def test_create_booking_offer_not_found(
        self,
        ac,
        fake_get_current_user,
    ):
        appointment_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        payload = {
            "offer_id": 99999,
            "appointment_time": appointment_time,
        }

        response = await ac.post("/bookings/create", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Offer is not found or it is inactive"

    async def test_create_booking_offer_not_approved(
        self,
        ac,
        fake_get_current_user,
        seed_pending_offer,
    ):
        appointment_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        payload = {
            "offer_id": seed_pending_offer.id,
            "appointment_time": appointment_time,
        }

        response = await ac.post("/bookings/create", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Offer is not found or it is inactive"

    async def test_create_booking_validation_error(
        self,
        ac,
        fake_get_current_user,
    ):
        payload = {
            "offer_id": "not_an_int",
            "appointment_time": "invalid_date_format",
        }

        response = await ac.post("/bookings/create", json=payload)
        assert response.status_code == 422

    async def test_create_booking_unauthorized(
        self,
        ac,
        seed_approved_offer,
    ):
        appointment_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        payload = {
            "offer_id": seed_approved_offer.id,
            "appointment_time": appointment_time,
        }

        response = await ac.post("/bookings/create", json=payload)
        assert response.status_code == 401


class TestGetBookings:
    @pytest.fixture
    async def seed_user_bookings(self, get_test_session, booking_factory):
        b1 = await booking_factory(status=BookingStatus.PENDING, days_ahead=1)
        b2 = await booking_factory(status=BookingStatus.CONFIRMED, days_ahead=2)
        await get_test_session.commit()
        await get_test_session.refresh(b1)
        await get_test_session.refresh(b2)
        return [b1, b2]

    @pytest.fixture
    async def seed_other_user_booking(
        self, get_test_session, user_factory, booking_factory
    ):
        other_user = await user_factory(role=UserRole.CLIENT)
        booking = await booking_factory(
            user_id=other_user.id,
            status=BookingStatus.PENDING,
            days_ahead=3,
        )
        await get_test_session.commit()
        await get_test_session.refresh(booking)
        return booking

    async def test_get_current_bookings_success(
        self,
        ac,
        fake_get_current_user,
        fake_get_redis,
        seed_user_bookings,
        seed_other_user_booking,
    ):
        response = await ac.get("/bookings/my")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        booking_ids = [item["id"] for item in data]
        assert seed_user_bookings[0].id in booking_ids
        assert seed_user_bookings[1].id in booking_ids
        assert seed_other_user_booking.id not in booking_ids

        cache_key = fake_get_redis.build_key(
            "bookings", "user", fake_get_current_user.id
        )
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert len(cached_data) == 2

    async def test_get_current_bookings_returns_cached_data(
        self,
        ac,
        fake_get_current_user,
        fake_get_redis,
    ):
        cache_key = fake_get_redis.build_key(
            "bookings", "user", fake_get_current_user.id
        )
        cached_payload = [
            {
                "id": 999,
                "user_id": fake_get_current_user.id,
                "offer_id": 1,
                "status": BookingStatus.PENDING,
                "appointment_time": "2026-09-15T12:00:00Z",
                "created_at": "2026-09-12T10:00:00Z",
                "updated_at": "2026-09-12T10:00:00Z",
            }
        ]
        await fake_get_redis.setc(cache_key, cached_payload, CacheTTL.FAST)

        response = await ac.get("/bookings/my")
        assert response.status_code == 200
        assert response.json() == cached_payload

    async def test_get_current_bookings_empty_list(
        self,
        ac,
        fake_get_current_user,
        fake_get_redis,
    ):
        response = await ac.get("/bookings/my")
        assert response.status_code == 200
        assert response.json() == []

        cache_key = fake_get_redis.build_key(
            "bookings", "user", fake_get_current_user.id
        )
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data == []

    async def test_get_current_bookings_unauthorized(
        self,
        ac,
    ):
        response = await ac.get("/bookings/my")
        assert response.status_code == 401

    async def test_get_booking_by_id_owner_success(
        self,
        ac,
        fake_get_current_user,
        fake_get_redis,
        seed_user_bookings,
    ):
        target_booking = seed_user_bookings[0]

        response = await ac.get(f"/bookings/{target_booking.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_booking.id
        assert data["user_id"] == fake_get_current_user.id
        assert data["offer_id"] == target_booking.offer_id

        cache_key = fake_get_redis.build_key("bookings", "id", target_booking.id)
        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert cached_data["id"] == target_booking.id

    async def test_get_booking_by_id_returns_cached_data(
        self,
        ac,
        fake_get_current_user,
        fake_get_redis,
    ):
        booking_id = 456
        cache_key = fake_get_redis.build_key("bookings", "id", booking_id)
        cached_payload = {
            "id": booking_id,
            "user_id": fake_get_current_user.id,
            "offer_id": 10,
            "status": BookingStatus.CONFIRMED,
            "appointment_time": "2026-09-20T14:00:00Z",
            "created_at": "2026-09-12T10:00:00Z",
            "updated_at": "2026-09-12T10:00:00Z",
        }
        await fake_get_redis.setc(cache_key, cached_payload, CacheTTL.FAST)

        response = await ac.get(f"/bookings/{booking_id}")
        assert response.status_code == 200
        assert response.json() == cached_payload

    async def test_get_booking_by_id_cached_access_denied(
        self,
        ac,
        fake_get_current_user,
        fake_get_redis,
    ):
        booking_id = 789
        cache_key = fake_get_redis.build_key("bookings", "id", booking_id)
        cached_payload = {
            "id": booking_id,
            "user_id": fake_get_current_user.id + 999,
            "offer_id": 10,
            "status": BookingStatus.PENDING,
            "appointment_time": "2026-09-20T14:00:00Z",
            "created_at": "2026-09-12T10:00:00Z",
            "updated_at": "2026-09-12T10:00:00Z",
        }
        await fake_get_redis.setc(cache_key, cached_payload, CacheTTL.FAST)

        response = await ac.get(f"/bookings/{booking_id}")
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    async def test_get_booking_by_id_admin_success(
        self,
        ac,
        seed_other_user_booking,
        fake_get_admin_user,
    ):
        response = await ac.get(f"/bookings/{seed_other_user_booking.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == seed_other_user_booking.id
        assert data["user_id"] == seed_other_user_booking.user_id

    async def test_get_booking_by_id_access_denied(
        self,
        ac,
        fake_get_current_user,
        seed_other_user_booking,
    ):
        response = await ac.get(f"/bookings/{seed_other_user_booking.id}")
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    async def test_get_booking_by_id_not_found(
        self,
        ac,
        fake_get_current_user,
    ):
        response = await ac.get("/bookings/9999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Booking not found"

    async def test_get_booking_by_id_unauthorized(self, ac):
        response = await ac.get("/bookings/1")
        assert response.status_code == 401


class TestCancelBooking:
    @pytest.fixture
    async def seed_pending_booking(self, get_test_session, booking_factory):
        booking = await booking_factory(status=BookingStatus.PENDING, days_ahead=2)
        await get_test_session.commit()
        await get_test_session.refresh(booking)
        return booking

    @pytest.fixture
    async def seed_other_user_booking(
        self, get_test_session, user_factory, booking_factory
    ):
        other_user = await user_factory(role=UserRole.CLIENT)
        booking = await booking_factory(
            user_id=other_user.id,
            status=BookingStatus.PENDING,
            days_ahead=2,
        )
        await get_test_session.commit()
        await get_test_session.refresh(booking)
        return booking

    async def test_cancel_booking_success(
        self,
        ac,
        get_test_session,
        fake_get_current_user,
        fake_get_redis,
        seed_pending_booking,
    ):
        cache_key_user = fake_get_redis.build_key(
            "bookings", "user", fake_get_current_user.id
        )
        await fake_get_redis.setc(cache_key_user, [{"test": "data"}], CacheTTL.FAST)

        response = await ac.patch(f"/bookings/{seed_pending_booking.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == seed_pending_booking.id
        assert data["status"] == BookingStatus.CANCELLED

        query = select(Booking).where(Booking.id == seed_pending_booking.id)
        result = await get_test_session.execute(query)
        booking_in_db = result.scalar_one()

        assert booking_in_db.status == BookingStatus.CANCELLED
        assert await fake_get_redis.getc(cache_key_user) is None

        cache_key_id = fake_get_redis.build_key(
            "bookings", "id", seed_pending_booking.id
        )
        assert await fake_get_redis.getc(cache_key_id) is None

    async def test_cancel_confirmed_booking_success(
        self,
        ac,
        get_test_session,
        fake_get_current_user,
        seed_pending_booking,
    ):
        seed_pending_booking.status = BookingStatus.CONFIRMED
        await get_test_session.commit()

        response = await ac.patch(f"/bookings/{seed_pending_booking.id}")
        assert response.status_code == 200
        assert response.json()["status"] == BookingStatus.CANCELLED

    async def test_cancel_booking_by_admin(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        seed_other_user_booking,
        fake_get_admin_user,
    ):
        owner_cache_key = fake_get_redis.build_key(
            "bookings", "user", seed_other_user_booking.user_id
        )
        await fake_get_redis.setc(owner_cache_key, [{"owner": "data"}], CacheTTL.FAST)

        response = await ac.patch(f"/bookings/{seed_other_user_booking.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == seed_other_user_booking.id
        assert data["status"] == BookingStatus.CANCELLED

        query = select(Booking).where(Booking.id == seed_other_user_booking.id)
        result = await get_test_session.execute(query)
        booking_in_db = result.scalar_one()
        assert booking_in_db.status == BookingStatus.CANCELLED

        assert await fake_get_redis.getc(owner_cache_key) is None

    @pytest.mark.parametrize(
        "invalid_status",
        [
            BookingStatus.CANCELLED,
            BookingStatus.COMPLETED,
            BookingStatus.NO_SHOW,
        ],
    )
    async def test_cancel_booking_invalid_status(
        self,
        ac,
        get_test_session,
        fake_get_current_user,
        seed_pending_booking,
        invalid_status,
    ):
        seed_pending_booking.status = invalid_status
        await get_test_session.commit()

        response = await ac.patch(f"/bookings/{seed_pending_booking.id}")
        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == f"Cannot cancel booking with status: {invalid_status}"
        )

    async def test_cancel_booking_access_denied(
        self,
        ac,
        fake_get_current_user,
        seed_other_user_booking,
    ):
        response = await ac.patch(f"/bookings/{seed_other_user_booking.id}")
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    async def test_cancel_booking_not_found(
        self,
        ac,
        fake_get_current_user,
    ):
        response = await ac.patch("/bookings/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Booking not found"

    async def test_cancel_booking_unauthorized(self, ac):
        response = await ac.patch("/bookings/1")
        assert response.status_code == 401
