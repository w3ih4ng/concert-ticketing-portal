from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import User
from concert_portal.security import password_hash


def _create_user(
    session: Session,
    *,
    name: str,
    email: str,
    role: str,
) -> User:
    """Create a user for navigation tests."""

    user = User(
        name=name,
        email=email,
        phone="0123456789",
        role=role,
        password_hash=password_hash.hash(
            "Password123",
        ),
    )

    session.add(
        user,
    )
    session.commit()
    session.refresh(
        user,
    )

    return user


def _login(
    client: TestClient,
    email: str,
) -> None:
    """Log in a test user."""

    response = client.post(
        "/login",
        data={
            "email": email,
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_guest_navigation(
    client: TestClient,
) -> None:
    """Guests only see public navigation."""

    response = client.get("/")

    assert response.status_code == 200

    assert "Discover" in response.text
    assert "Login" in response.text
    assert "Register" in response.text

    assert "Create Concert" not in response.text
    assert "My Bookings" not in response.text
    assert "Verify Ticket" not in response.text
    assert "Staff Accounts" not in response.text


def test_attendee_navigation(
    client: TestClient,
    session: Session,
) -> None:
    """Attendees only see attendee navigation."""

    _create_user(
        session,
        name="Attendee User",
        email="attendee@example.com",
        role="attendee",
    )

    _login(
        client,
        "attendee@example.com",
    )

    response = client.get("/")

    assert response.status_code == 200

    assert "Discover" in response.text
    assert "My Bookings" in response.text
    assert "Profile" in response.text
    assert "Logout" in response.text

    assert "Create Concert" not in response.text
    assert "Verify Ticket" not in response.text
    assert "Staff Accounts" not in response.text


def test_staff_navigation(
    client: TestClient,
    session: Session,
) -> None:
    """Staff only see staff navigation."""

    _create_user(
        session,
        name="Staff User",
        email="staff@example.com",
        role="staff",
    )

    _login(
        client,
        "staff@example.com",
    )

    response = client.get(
        "/staff/dashboard",
    )

    assert response.status_code == 200

    assert "Dashboard" in response.text
    assert "Verify Ticket" in response.text
    assert "Profile" in response.text
    assert "Logout" in response.text

    assert "Create Concert" not in response.text
    assert "My Bookings" not in response.text
    assert "Staff Accounts" not in response.text


def test_admin_navigation(
    client: TestClient,
    session: Session,
) -> None:
    """Admins only see administrative navigation."""

    _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        "admin@example.com",
    )

    response = client.get(
        "/admin/dashboard",
    )

    assert response.status_code == 200

    assert "Dashboard" in response.text
    assert "Organisers" in response.text
    assert "Concerts" in response.text
    assert "Payments" in response.text
    assert "Staff Accounts" in response.text
    assert "Profile" in response.text
    assert "Logout" in response.text

    assert "Create Concert" not in response.text
    assert "My Bookings" not in response.text
    assert "Verify Ticket" not in response.text
