from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlmodel import Session

from concert_portal.models import OrganiserProfile, User

password_hash = PasswordHash.recommended()


def _create_user(
    session: Session,
    *,
    email: str = "attendee@example.com",
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


def _login_attendee(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(session)

    response = client.post(
        "/login",
        data={
            "email": "attendee@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_logout_route_redirects_to_login(
    client: TestClient,
    session: Session,
) -> None:
    _login_attendee(client, session)

    response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?logged_out=true"


def test_logout_clears_session(
    client: TestClient,
    session: Session,
) -> None:
    _login_attendee(client, session)

    before_logout = client.get(
        "/login",
        follow_redirects=False,
    )

    assert before_logout.status_code == 303
    assert before_logout.headers["location"] == "/"

    logout_response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert logout_response.status_code == 303

    after_logout = client.get(
        "/login",
        follow_redirects=False,
    )

    assert after_logout.status_code == 200
    assert "<h1>Login</h1>" in after_logout.text


def test_logout_success_message_is_displayed(
    client: TestClient,
    session: Session,
) -> None:
    _login_attendee(client, session)

    logout_response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == ("/login?logged_out=true")

    login_response = client.get(
        logout_response.headers["location"],
    )

    assert login_response.status_code == 200
    assert "You have been logged out successfully." in login_response.text


def test_logout_button_is_visible_when_logged_in(
    client: TestClient,
    session: Session,
) -> None:
    _login_attendee(client, session)

    response = client.get("/")

    assert response.status_code == 200
    assert 'action="/logout"' in response.text
    assert 'type="submit"' in response.text
    assert "Logout" in response.text
    assert 'href="/login"' not in response.text


def test_login_link_is_visible_when_logged_out(
    client: TestClient,
) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/login"' in response.text
    assert 'action="/logout"' not in response.text


def test_logout_without_active_session_is_safe(
    client: TestClient,
) -> None:
    response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?logged_out=true"


def test_logout_blocks_access_to_protected_dashboard(
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
    assert login_response.headers["location"] == "/organiser/dashboard"

    dashboard_before_logout = client.get(
        "/organiser/dashboard",
        follow_redirects=False,
    )

    assert dashboard_before_logout.status_code == 200

    logout_response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert logout_response.status_code == 303

    dashboard_after_logout = client.get(
        "/organiser/dashboard",
        follow_redirects=False,
    )

    assert dashboard_after_logout.status_code == 303
    assert dashboard_after_logout.headers["location"] == "/login"
