from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from main import app
from src.common.enums import CacheTTL, ModerationStatus, UserRole
from src.core.dependencies import get_current_doctor, get_current_user
from src.core.security import hash_pwd
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead
from src.modules.reviews.models import Review
from src.modules.users.models import User
from src.modules.users.schemas import UserRead


class TestCreateReview:
    @pytest.fixture
    async def seed_doctor(self, get_test_session) -> Doctor:
        now = datetime.now(UTC).replace(tzinfo=None)

        user = User(
            name="Review Doctor User",
            email="doc_review_target@test.com",
            password=hash_pwd("pwd"),
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
            experience_years=10,
            bio="Practicing specialist",
            min_price=100,
            clinic="Main City Clinic",
            rating_avg=4.0,
            reviews_count=1,
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.commit()
        await get_test_session.refresh(doctor)
        return doctor

    async def test_create_review_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        fake_get_current_user,
        seed_doctor,
    ):
        cache_key = fake_get_redis.build_key("doctors", "items", seed_doctor.id)
        await fake_get_redis.setc(cache_key, {"cached": "doctor"}, CacheTTL.FAST)
        assert await fake_get_redis.getc(cache_key) is not None

        payload = {
            "doctor_id": seed_doctor.id,
            "rating": 5,
            "comment": "Great doctor, very attentive and professional!",
        }

        response = await ac.post("/reviews/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["id"] is not None
        assert data["user_id"] == fake_get_current_user.id
        assert data["doctor_id"] == seed_doctor.id
        assert data["rating"] == 5
        assert data["comment"] == payload["comment"]
        assert data["status"] == ModerationStatus.APPROVED

        query_review = select(Review).where(Review.id == data["id"])
        review_res = await get_test_session.execute(query_review)
        db_review = review_res.scalar_one_or_none()
        assert db_review is not None
        assert db_review.user_id == fake_get_current_user.id
        assert db_review.rating == 5

        query_doctor = select(Doctor).where(Doctor.id == seed_doctor.id)
        doctor_res = await get_test_session.execute(query_doctor)
        db_doctor = doctor_res.scalar_one()
        assert db_doctor.reviews_count == 2
        assert db_doctor.rating_avg == 4.5

        assert await fake_get_redis.getc(cache_key) is None

    async def test_create_review_already_left(
        self,
        ac,
        fake_get_current_user,
        seed_doctor,
    ):
        payload = {
            "doctor_id": seed_doctor.id,
            "rating": 4,
            "comment": "First review feedback.",
        }

        first_response = await ac.post("/reviews/", json=payload)
        assert first_response.status_code == 201

        second_response = await ac.post("/reviews/", json=payload)
        assert second_response.status_code == 409
        assert (
            second_response.json()["detail"]
            == "You have already left feedback to this doctor"
        )

    @pytest.mark.parametrize(
        "invalid_payload",
        [
            {"doctor_id": 1, "rating": 0, "comment": "Low rating"},
            {"doctor_id": 1, "rating": 6, "comment": "High rating"},
            {"doctor_id": 1, "rating": 5, "comment": "A" * 351},
            {"doctor_id": "not_an_int", "rating": 5, "comment": "Valid comment"},
        ],
    )
    async def test_create_review_validation_error(
        self,
        ac,
        fake_get_current_user,
        invalid_payload,
    ):
        response = await ac.post("/reviews/", json=invalid_payload)
        assert response.status_code == 422

    async def test_create_review_unauthorized(
        self,
        ac,
        seed_doctor,
    ):
        payload = {
            "doctor_id": seed_doctor.id,
            "rating": 5,
            "comment": "Attempting to post anonymously.",
        }
        response = await ac.post("/reviews/", json=payload)
        assert response.status_code == 401


class TestReadReviews:
    @pytest.fixture
    async def seed_reviews_setup(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        doc_user = User(
            name="Target Doctor User",
            email="target_doc_read@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        user1 = User(
            name="Reviewer One",
            email="rev1@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.CLIENT,
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            name="Reviewer Two",
            email="rev2@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.CLIENT,
            created_at=now,
            updated_at=now,
        )
        user3 = User(
            name="Reviewer Three",
            email="rev3@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.CLIENT,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([doc_user, user1, user2, user3])
        await get_test_session.flush()

        doctor = Doctor(
            user_id=doc_user.id,
            education="Med School",
            experience_years=5,
            bio="Bio",
            min_price=100,
            clinic="Clinic",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.flush()

        rev1 = Review(
            doctor_id=doctor.id,
            user_id=user1.id,
            rating=5,
            comment="Excellent service!",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        rev2 = Review(
            doctor_id=doctor.id,
            user_id=user2.id,
            rating=2,
            comment="Bad experience.",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        rev3 = Review(
            doctor_id=doctor.id,
            user_id=user3.id,
            rating=4,
            comment="Under moderation review.",
            status=ModerationStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        get_test_session.add_all([rev1, rev2, rev3])
        await get_test_session.commit()
        await get_test_session.refresh(doctor)
        await get_test_session.refresh(rev1)
        await get_test_session.refresh(rev2)
        await get_test_session.refresh(rev3)

        return {
            "doctor": doctor,
            "reviews": [rev1, rev2, rev3],
        }

    async def test_get_reviews_default_list(
        self,
        ac,
        seed_reviews_setup,
    ):
        doctor_id = seed_reviews_setup["doctor"].id
        response = await ac.get(
            f"/reviews/{doctor_id}?status={ModerationStatus.APPROVED}"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert all(
            item["status"] == ModerationStatus.APPROVED for item in data["items"]
        )

    async def test_get_reviews_filter_by_rating(
        self,
        ac,
        seed_reviews_setup,
    ):
        doctor_id = seed_reviews_setup["doctor"].id
        response = await ac.get(
            f"/reviews/{doctor_id}?status={ModerationStatus.APPROVED}&rating=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["rating"] == 5

    async def test_get_reviews_filter_is_positive_true(
        self,
        ac,
        seed_reviews_setup,
    ):
        doctor_id = seed_reviews_setup["doctor"].id
        response = await ac.get(
            f"/reviews/{doctor_id}?status={ModerationStatus.APPROVED}&is_positive=true"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["rating"] == 5

    async def test_get_reviews_filter_is_positive_false(
        self,
        ac,
        seed_reviews_setup,
    ):
        doctor_id = seed_reviews_setup["doctor"].id
        response = await ac.get(
            f"/reviews/{doctor_id}?status={ModerationStatus.APPROVED}&is_positive=false"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["rating"] == 2

    async def test_get_reviews_filter_by_status_pending(
        self,
        ac,
        seed_reviews_setup,
    ):
        doctor_id = seed_reviews_setup["doctor"].id
        response = await ac.get(
            f"/reviews/{doctor_id}?status={ModerationStatus.PENDING}"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == ModerationStatus.PENDING

    async def test_get_reviews_pagination(
        self,
        ac,
        seed_reviews_setup,
    ):
        doctor_id = seed_reviews_setup["doctor"].id
        response = await ac.get(
            f"/reviews/{doctor_id}?status={ModerationStatus.APPROVED}&limit=1&offset=0"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1
        assert data["limit"] == 1
        assert data["offset"] == 0

    async def test_get_reviews_missing_required_status(
        self,
        ac,
        seed_reviews_setup,
    ):
        doctor_id = seed_reviews_setup["doctor"].id
        response = await ac.get(f"/reviews/{doctor_id}")
        assert response.status_code == 422


class TestUpdateReviews:
    @pytest.fixture
    async def seed_review_update_setup(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        doc_user = User(
            name="Doctor For Appeals",
            email="doc_appeal@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        other_doc_user = User(
            name="Other Doctor For Appeals",
            email="other_doc_appeal@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        client_user = User(
            name="Client Reviewer",
            email="client_rev@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.CLIENT,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([doc_user, other_doc_user, client_user])
        await get_test_session.flush()

        doc1 = Doctor(
            user_id=doc_user.id,
            education="Med Academy 1",
            experience_years=8,
            bio="Bio 1",
            min_price=100,
            clinic="Clinic 1",
            rating_avg=4.0,
            reviews_count=2,
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        doc2 = Doctor(
            user_id=other_doc_user.id,
            education="Med Academy 2",
            experience_years=5,
            bio="Bio 2",
            min_price=80,
            clinic="Clinic 2",
            rating_avg=5.0,
            reviews_count=1,
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([doc1, doc2])
        await get_test_session.flush()

        review = Review(
            doctor_id=doc1.id,
            user_id=client_user.id,
            rating=5,
            comment="Excellent consultation experience!",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(review)
        await get_test_session.commit()
        await get_test_session.refresh(doc1)
        await get_test_session.refresh(doc2)
        await get_test_session.refresh(review)

        return {
            "doctor": doc1,
            "foreign_doctor": doc2,
            "review": review,
        }

    async def test_doctor_remove_review_request_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        seed_review_update_setup,
    ):
        doc = seed_review_update_setup["doctor"]
        target_review = seed_review_update_setup["review"]
        doc_read = DoctorRead.model_validate(doc)

        cache_key = fake_get_redis.build_key("doctors", "items", doc.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.patch(f"/reviews/review/{target_review.id}/appeal")
            assert response.status_code == 200

            data = response.json()
            assert data["id"] == target_review.id
            assert data["status"] == ModerationStatus.PENDING

            query = select(Review).where(Review.id == target_review.id)
            result = await get_test_session.execute(query)
            db_review = result.scalar_one()
            assert db_review.status == ModerationStatus.PENDING
            assert await fake_get_redis.getc(cache_key) is None
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)

    async def test_doctor_remove_review_request_foreign_forbidden(
        self,
        ac,
        seed_review_update_setup,
    ):
        foreign_doc = seed_review_update_setup["foreign_doctor"]
        target_review = seed_review_update_setup["review"]
        doc_read = DoctorRead.model_validate(foreign_doc)

        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.patch(f"/reviews/review/{target_review.id}/appeal")
            assert response.status_code == 403
            assert response.json()["detail"] == "You can only delete your own reviews"
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)

    async def test_admin_approve_deletion_success(
        self,
        ac,
        get_test_session,
        fake_get_admin_user,
        fake_get_redis,
        seed_review_update_setup,
    ):
        doc = seed_review_update_setup["doctor"]
        target_review = seed_review_update_setup["review"]

        cache_key = fake_get_redis.build_key("doctors", "items", doc.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        response = await ac.patch(
            f"/reviews/review/{target_review.id}/approve"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_review.id
        assert data["status"] == ModerationStatus.REJECTED

        query_rev = select(Review).where(Review.id == target_review.id)
        res_rev = await get_test_session.execute(query_rev)
        db_review = res_rev.scalar_one()
        assert db_review.status == ModerationStatus.REJECTED

        query_doc = select(Doctor).where(Doctor.id == doc.id)
        res_doc = await get_test_session.execute(query_doc)
        db_doctor = res_doc.scalar_one()
        assert db_doctor.reviews_count == 1
        assert db_doctor.rating_avg == 3.0
        assert await fake_get_redis.getc(cache_key) is None

    async def test_admin_reject_deletion_success(
        self,
        ac,
        get_test_session,
        fake_get_admin_user,
        fake_get_redis,
        seed_review_update_setup,
    ):
        doc = seed_review_update_setup["doctor"]
        target_review = seed_review_update_setup["review"]
        target_review.status = ModerationStatus.PENDING
        await get_test_session.commit()

        cache_key = fake_get_redis.build_key("doctors", "items", doc.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        response = await ac.patch(f"/reviews/review/{target_review.id}/reject")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == target_review.id
        assert data["status"] == ModerationStatus.APPROVED

        query_rev = select(Review).where(Review.id == target_review.id)
        res_rev = await get_test_session.execute(query_rev)
        db_review = res_rev.scalar_one()
        assert db_review.status == ModerationStatus.APPROVED
        assert await fake_get_redis.getc(cache_key) is None

    async def test_admin_approve_deletion_unauthorized(
        self,
        ac,
        seed_review_update_setup,
    ):
        target_review = seed_review_update_setup["review"]
        response = await ac.patch(
            f"/reviews/review/{target_review.id}/approve"
        )
        assert response.status_code == 401

    async def test_admin_reject_deletion_unauthorized(
        self,
        ac,
        seed_review_update_setup,
    ):
        target_review = seed_review_update_setup["review"]
        response = await ac.patch(f"/reviews/review/{target_review.id}/reject")
        assert response.status_code == 401

    async def test_appeal_review_not_found(
        self,
        ac,
        seed_review_update_setup,
    ):
        doc = seed_review_update_setup["doctor"]
        doc_read = DoctorRead.model_validate(doc)
        app.dependency_overrides[get_current_doctor] = lambda: doc_read
        try:
            response = await ac.patch("/reviews/review/99999/appeal")
            assert response.status_code == 404
            assert response.json()["detail"] == "Review not found"
        finally:
            app.dependency_overrides.pop(get_current_doctor, None)


class TestDeleteReviews:
    @pytest.fixture
    async def seed_review_delete_setup(self, get_test_session):
        now = datetime.now(UTC).replace(tzinfo=None)

        doc_user = User(
            name="Doctor Delete Target",
            email="doc_del_target@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.DOCTOR,
            created_at=now,
            updated_at=now,
        )
        owner_user = User(
            name="Review Owner",
            email="owner_rev@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.CLIENT,
            created_at=now,
            updated_at=now,
        )
        foreign_user = User(
            name="Foreign User",
            email="foreign_rev@test.com",
            password=hash_pwd("pwd"),
            role=UserRole.CLIENT,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add_all([doc_user, owner_user, foreign_user])
        await get_test_session.flush()

        doctor = Doctor(
            user_id=doc_user.id,
            education="Med Academy Delete",
            experience_years=7,
            bio="Delete bio",
            min_price=100,
            clinic="Delete Clinic",
            rating_avg=4.0,
            reviews_count=2,
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.flush()

        review = Review(
            doctor_id=doctor.id,
            user_id=owner_user.id,
            rating=5,
            comment="Review to be deleted by its author",
            status=ModerationStatus.APPROVED,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(review)
        await get_test_session.commit()
        await get_test_session.refresh(doctor)
        await get_test_session.refresh(owner_user)
        await get_test_session.refresh(foreign_user)
        await get_test_session.refresh(review)

        return {
            "doctor": doctor,
            "owner_user": owner_user,
            "foreign_user": foreign_user,
            "review": review,
        }

    async def test_remove_review_by_user_success(
        self,
        ac,
        get_test_session,
        fake_get_redis,
        seed_review_delete_setup,
    ):
        doc = seed_review_delete_setup["doctor"]
        owner_user = seed_review_delete_setup["owner_user"]
        target_review = seed_review_delete_setup["review"]
        owner_read = UserRead.model_validate(owner_user)

        cache_key = fake_get_redis.build_key("doctors", "items", doc.id)
        await fake_get_redis.setc(cache_key, {"cached": "data"}, CacheTTL.FAST)

        app.dependency_overrides[get_current_user] = lambda: owner_read
        try:
            response = await ac.patch(f"/reviews/{target_review.id}")
            assert response.status_code == 204

            query_rev = select(Review).where(Review.id == target_review.id)
            res_rev = await get_test_session.execute(query_rev)
            assert res_rev.scalar_one_or_none() is None

            query_doc = select(Doctor).where(Doctor.id == doc.id)
            res_doc = await get_test_session.execute(query_doc)
            db_doctor = res_doc.scalar_one()
            assert db_doctor.reviews_count == 1
            assert db_doctor.rating_avg == 3.0

            assert await fake_get_redis.getc(cache_key) is None
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_remove_review_by_user_foreign_forbidden(
        self,
        ac,
        get_test_session,
        seed_review_delete_setup,
    ):
        foreign_user = seed_review_delete_setup["foreign_user"]
        target_review = seed_review_delete_setup["review"]
        foreign_read = UserRead.model_validate(foreign_user)

        app.dependency_overrides[get_current_user] = lambda: foreign_read
        try:
            response = await ac.patch(f"/reviews/{target_review.id}")
            assert response.status_code == 403
            assert response.json()["detail"] == "You can only delete your own reviews"

            query_rev = select(Review).where(Review.id == target_review.id)
            res_rev = await get_test_session.execute(query_rev)
            assert res_rev.scalar_one_or_none() is not None
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_remove_review_by_user_not_found(
        self,
        ac,
        seed_review_delete_setup,
    ):
        owner_user = seed_review_delete_setup["owner_user"]
        owner_read = UserRead.model_validate(owner_user)

        app.dependency_overrides[get_current_user] = lambda: owner_read
        try:
            response = await ac.patch("/reviews/99999")
            assert response.status_code == 404
            assert response.json()["detail"] == "Review not found"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_remove_review_by_user_unauthorized(
        self,
        ac,
        seed_review_delete_setup,
    ):
        target_review = seed_review_delete_setup["review"]
        response = await ac.patch(f"/reviews/{target_review.id}")
        assert response.status_code == 401
