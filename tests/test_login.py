from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlmodel import Session

from concert_portal.models import OrganiserProfile, User

password_hash = PasswordHash.recommended()


def _create_user(
    session: Session,
    *,
    email: str,
    password: str = "Password123",
    role: str = "attendee",
) -> User:
    user = User(
        name="Test User",
        email=email,
        phone="012-3456789",
        role=role,
        password_hash=password_hash.hash(password),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def test_login_page_is_available(client: TestClient) -> None:
    response = client.get("/login")

    assert response.status_code == 200
    assert "<h1>Login</h1>" in response.text
    assert 'action="/login"' in response.text


def test_login_handles_blank_fields(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={
            "email": "",
            "password": "",
        },
    )

    assert response.status_code == 422
    assert "Invalid email or password." in response.text


def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={
            "email": "missing@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 401
    assert "Invalid email or password." in response.text


def test_login_rejects_incorrect_password(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
    )

    response = client.post(
        "/login",
        data={
            "email": "attendee@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401
    assert "Invalid email or password." in response.text


def test_attendee_login_redirects_to_concerts(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
    )

    response = client.post(
        "/login",
        data={
            "email": "  ATTENDEE@EXAMPLE.COM ",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_successful_login_creates_session(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        email="attendee@example.com",
    )

    response = client.post(
        "/login",
        data={
            "email": "attendee@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert user.id is not None
    assert client.cookies.get("concert_portal_session") is not None


def test_pending_organiser_cannot_login(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        email="organiser@example.com",
        role="organiser",
    )

    assert user.id is not None

    profile = OrganiserProfile(
        user_id=user.id,
        organisation_name="Live Events",
        registration_number="REG-123",
        organisation_address="Kuala Lumpur",
        status="pending",
    )

    session.add(profile)
    session.commit()

    response = client.post(
        "/login",
        data={
            "email": "organiser@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 403
    assert "pending approval" in response.text


def test_approved_organiser_redirects_to_dashboard(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        email="organiser@example.com",
        role="organiser",
    )

    assert user.id is not None

    profile = OrganiserProfile(
        user_id=user.id,
        organisation_name="Live Events",
        registration_number="REG-123",
        organisation_address="Kuala Lumpur",
        status="approved",
    )

    session.add(profile)
    session.commit()

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


def test_organiser_dashboard_requires_login(
    client: TestClient,
) -> None:
    response = client.get(
        "/organiser/dashboard",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_approved_organiser_can_view_dashboard(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        email="organiser@example.com",
        role="organiser",
    )

    assert user.id is not None

    profile = OrganiserProfile(
        user_id=user.id,
        organisation_name="Live Events",
        registration_number="REG-123",
        organisation_address="Kuala Lumpur",
        status="approved",
    )

    session.add(profile)
    session.commit()

    login_response = client.post(
        "/login",
        data={
            "email": "organiser@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    dashboard_response = client.get("/organiser/dashboard")

    assert dashboard_response.status_code == 200
    assert "Welcome, Test User" in dashboard_response.text
    assert "logged in as" in dashboard_response.text


def test_login_api_returns_safe_user_data(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
    )

    response = client.post(
        "/users/login",
        json={
            "email": "attendee@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "attendee@example.com"
    assert data["role"] == "attendee"
    assert data["redirect_url"] == "/"
    assert "password" not in data
    assert "password_hash" not in data


def test_login_api_rejects_bad_credentials(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/login",
        json={
            "email": "missing@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_logged_in_user_is_redirected_away_from_login(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
    )

    login_response = client.post(
        "/login",
        data={
            "email": "attendee@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    second_response = client.get(
        "/login",
        follow_redirects=False,
    )

    assert second_response.status_code == 303
    assert second_response.headers["location"] == "/"
