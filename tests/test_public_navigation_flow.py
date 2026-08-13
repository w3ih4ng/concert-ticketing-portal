from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import User
from concert_portal.security import password_hash


def test_home_page_is_portal_landing_page(
    client: TestClient,
) -> None:
    """The root route shows the public landing page."""

    response = client.get("/")

    assert response.status_code == 200
    assert "Find your next live experience." in response.text
    assert "Browse Concerts" in response.text
    assert "How It Works" in response.text


def test_discover_page_has_own_route(
    client: TestClient,
) -> None:
    """Concert discovery is available at /concerts."""

    response = client.get("/concerts")

    assert response.status_code == 200
    assert "Discover Concerts" in response.text
    assert 'action="/concerts"' in response.text


def test_registration_choice_page(
    client: TestClient,
) -> None:
    """Guests can choose attendee or organiser registration."""

    response = client.get("/register")

    assert response.status_code == 200

    assert "I want to attend concerts" in response.text
    assert "I want to organise concerts" in response.text
    assert "/register/attendee" in response.text
    assert "/register/organiser" in response.text


def test_guest_navigation_contains_home_and_discover(
    client: TestClient,
) -> None:
    """Guest navigation separates Home and Discover."""

    response = client.get("/")

    assert response.status_code == 200

    assert 'href="/"' in response.text
    assert "Home" in response.text

    assert 'href="/concerts"' in response.text
    assert "Discover" in response.text

    assert 'href="/register"' in response.text
    assert "Register" in response.text


def test_attendee_login_redirects_to_discover(
    client: TestClient,
    session: Session,
) -> None:
    """Attendees enter the concert discovery experience after login."""

    attendee = User(
        name="Attendee User",
        email="attendee.flow@example.com",
        phone="0123456789",
        role="attendee",
        password_hash=password_hash.hash(
            "Password123",
        ),
    )

    session.add(attendee)
    session.commit()

    response = client.post(
        "/login",
        data={
            "email": "attendee.flow@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/concerts"
