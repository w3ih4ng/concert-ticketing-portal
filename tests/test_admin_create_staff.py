from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import User
from concert_portal.security import password_hash
from concert_portal.services.users import find_user_by_email


def _create_user(
    session: Session,
    *,
    name: str,
    email: str,
    role: str,
) -> User:
    """Create a user for staff-account tests."""

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
    password: str = "Password123",
) -> None:
    """Login a test user."""

    response = client.post(
        "/login",
        data={
            "email": email,
            "password": password,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_staff_creation_requires_login(
    client: TestClient,
) -> None:
    """Unauthenticated users are redirected to login."""

    response = client.get(
        "/admin/staff/new",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_non_admin_cannot_access_staff_creation(
    client: TestClient,
    session: Session,
) -> None:
    """Non-admin users cannot access staff creation."""

    _create_user(
        session,
        name="Attendee",
        email="attendee@example.com",
        role="attendee",
    )

    _login(
        client,
        "attendee@example.com",
    )

    response = client.get(
        "/admin/staff/new",
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_admin_can_open_staff_creation_form(
    client: TestClient,
    session: Session,
) -> None:
    """Admin can access the staff-account form."""

    _create_user(
        session,
        name="Administrator",
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        "admin@example.com",
    )

    response = client.get(
        "/admin/staff/new",
    )

    assert response.status_code == 200
    assert "Create Staff Account" in response.text
    assert "Initial Password" in response.text


def test_admin_can_create_staff_account(
    client: TestClient,
    session: Session,
) -> None:
    """Admin can create a staff user."""

    _create_user(
        session,
        name="Administrator",
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        "admin@example.com",
    )

    response = client.post(
        "/admin/staff/new",
        data={
            "name": "Event Staff",
            "email": "staff@example.com",
            "phone": "0123456789",
            "password": "Password123",
        },
    )

    assert response.status_code == 201
    assert "Staff account created successfully." in response.text

    staff = find_user_by_email(
        "staff@example.com",
        session,
    )

    assert staff is not None
    assert staff.name == "Event Staff"
    assert staff.role == "staff"
    assert staff.phone == "0123456789"

    assert password_hash.verify(
        "Password123",
        staff.password_hash,
    )


def test_duplicate_staff_email_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    """Existing email addresses cannot be reused."""

    _create_user(
        session,
        name="Administrator",
        email="admin@example.com",
        role="admin",
    )

    _create_user(
        session,
        name="Existing User",
        email="existing@example.com",
        role="attendee",
    )

    _login(
        client,
        "admin@example.com",
    )

    response = client.post(
        "/admin/staff/new",
        data={
            "name": "Event Staff",
            "email": "existing@example.com",
            "phone": "0123456789",
            "password": "Password123",
        },
    )

    assert response.status_code == 409
    assert "An account with this email already exists." in response.text


def test_created_staff_can_login(
    client: TestClient,
    session: Session,
) -> None:
    """A staff account created by admin can log in."""

    _create_user(
        session,
        name="Administrator",
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        "admin@example.com",
    )

    response = client.post(
        "/admin/staff/new",
        data={
            "name": "Event Staff",
            "email": "staff@example.com",
            "phone": "0123456789",
            "password": "Password123",
        },
    )

    assert response.status_code == 201

    client.post(
        "/logout",
        follow_redirects=False,
    )

    response = client.post(
        "/login",
        data={
            "email": "staff@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/staff/dashboard"


def test_staff_role_cannot_be_supplied_by_form(
    client: TestClient,
    session: Session,
) -> None:
    """Created accounts always receive the staff role."""

    _create_user(
        session,
        name="Administrator",
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        "admin@example.com",
    )

    response = client.post(
        "/admin/staff/new",
        data={
            "name": "Event Staff",
            "email": "staff@example.com",
            "phone": "0123456789",
            "password": "Password123",
            "role": "admin",
        },
    )

    assert response.status_code == 201

    staff = find_user_by_email(
        "staff@example.com",
        session,
    )

    assert staff is not None
    assert staff.role == "staff"


def test_admin_dashboard_links_to_staff_creation(
    client: TestClient,
    session: Session,
) -> None:
    """Admin dashboard exposes staff-account management."""

    _create_user(
        session,
        name="Administrator",
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
    assert "Staff Accounts" in response.text
    assert "Create staff account" in response.text
    assert "/admin/staff/new" in response.text
