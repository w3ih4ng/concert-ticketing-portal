from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import OrganiserProfile, User
from concert_portal.security import password_hash


def _create_user(
    session: Session,
    *,
    email: str,
    role: str,
) -> User:
    user = User(
        name=f"Test {role.title()}",
        email=email,
        phone="012-3456789",
        role=role,
        password_hash=password_hash.hash("Password123"),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def _create_organiser(
    session: Session,
    *,
    email: str = "organiser@example.com",
    status: str = "pending",
) -> tuple[User, OrganiserProfile]:
    user = _create_user(
        session,
        email=email,
        role="organiser",
    )

    assert user.id is not None

    profile = OrganiserProfile(
        user_id=user.id,
        organisation_name="Test Events Sdn Bhd",
        registration_number="ORG-12345",
        organisation_address="Kuala Lumpur",
        status=status,
    )

    session.add(profile)
    session.commit()
    session.refresh(profile)

    return user, profile


def _login(
    client: TestClient,
    *,
    email: str,
) -> None:
    response = client.post(
        "/login",
        data={
            "email": email,
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_admin_organiser_page_requires_login(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin/organisers",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_non_admin_cannot_access_organiser_review(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
        role="attendee",
    )

    _login(
        client,
        email="attendee@example.com",
    )

    response = client.get(
        "/admin/organisers",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_admin_can_view_pending_organiser(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    _user, profile = _create_organiser(
        session,
    )

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get(
        "/admin/organisers",
    )

    assert response.status_code == 200
    assert "Organiser Account Approval" in response.text
    assert "Test Events Sdn Bhd" in response.text
    assert "ORG-12345" in response.text
    assert "organiser@example.com" in response.text
    assert f"/admin/organisers/{profile.id}/approve" in response.text
    assert f"/admin/organisers/{profile.id}/reject" in response.text


def test_approved_organisers_are_not_in_pending_list(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    _create_organiser(
        session,
        status="approved",
    )

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get(
        "/admin/organisers",
    )

    assert response.status_code == 200
    assert "No pending organiser requests" in response.text
    assert "Test Events Sdn Bhd" not in response.text


def test_admin_can_approve_organiser(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    _user, profile = _create_organiser(
        session,
    )

    assert profile.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/organisers/{profile.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/admin/organisers?message=",
    )

    session.refresh(profile)

    assert profile.status == "approved"


def test_approved_organiser_can_login(
    client: TestClient,
    session: Session,
) -> None:
    _user, profile = _create_organiser(
        session,
        status="approved",
    )

    response = client.post(
        "/login",
        data={
            "email": "organiser@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/organiser/dashboard"

    session.refresh(profile)

    assert profile.status == "approved"


def test_admin_can_reject_organiser(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    _user, profile = _create_organiser(
        session,
    )

    assert profile.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/organisers/{profile.id}/reject",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/admin/organisers?message=",
    )

    session.refresh(profile)

    assert profile.status == "rejected"


def test_rejected_organiser_cannot_login(
    client: TestClient,
    session: Session,
) -> None:
    _create_organiser(
        session,
        status="rejected",
    )

    response = client.post(
        "/login",
        data={
            "email": "organiser@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 403
    assert "Your organiser registration was rejected." in response.text


def test_pending_organiser_still_cannot_login(
    client: TestClient,
    session: Session,
) -> None:
    _create_organiser(
        session,
        status="pending",
    )

    response = client.post(
        "/login",
        data={
            "email": "organiser@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 403
    assert "Your organiser account is still pending approval." in response.text


def test_non_admin_cannot_approve_organiser(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
        role="attendee",
    )

    _user, profile = _create_organiser(
        session,
    )

    assert profile.id is not None

    _login(
        client,
        email="attendee@example.com",
    )

    response = client.post(
        f"/admin/organisers/{profile.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    session.refresh(profile)

    assert profile.status == "pending"


def test_missing_organiser_request_returns_404(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        "/admin/organisers/99999/approve",
        follow_redirects=False,
    )

    assert response.status_code == 404
