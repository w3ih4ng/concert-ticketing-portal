from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlmodel import Session

from concert_portal.models import (
    Booking,
    Concert,
    ETicket,
    Ticket,
    User,
)

password_hash = PasswordHash.recommended()


def _create_user(
    session: Session,
    *,
    name: str,
    email: str,
    role: str,
) -> User:
    """Create a user for staff verification tests."""

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
    """Login a test user."""

    response = client.post(
        "/login",
        data={
            "email": email,
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def _create_eticket(
    session: Session,
    *,
    status: str = "confirmed",
    code: str = "ET-VERIFY123456",
) -> ETicket:
    """Create an e-ticket for staff verification."""

    concert = Concert(
        title="Verification Concert",
        date="2030-12-22",
        venue="National Arena",
        organiser="Test Events",
    )

    session.add(
        concert,
    )
    session.commit()
    session.refresh(
        concert,
    )

    assert concert.id is not None

    ticket = Ticket(
        concert_id=concert.id,
        category="VIP",
        price=200.00,
        quantity=100,
    )

    session.add(
        ticket,
    )
    session.commit()
    session.refresh(
        ticket,
    )

    assert ticket.id is not None

    booking = Booking(
        ticket_id=ticket.id,
        attendee="Verified Attendee",
        quantity=2,
        status=status,
    )

    session.add(
        booking,
    )
    session.commit()
    session.refresh(
        booking,
    )

    assert booking.id is not None

    eticket = ETicket(
        booking_id=booking.id,
        ticket_code=code,
    )

    session.add(
        eticket,
    )
    session.commit()
    session.refresh(
        eticket,
    )

    return eticket


def test_ticket_verification_requires_login(
    client: TestClient,
) -> None:
    """Unauthenticated users are redirected to login."""

    response = client.get(
        "/staff/tickets/verify",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_non_staff_cannot_access_ticket_verification(
    client: TestClient,
    session: Session,
) -> None:
    """Attendees cannot access the staff verification page."""

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

    response = client.get(
        "/staff/tickets/verify",
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_staff_can_open_ticket_verification_page(
    client: TestClient,
    session: Session,
) -> None:
    """Staff can access the ticket verification form."""

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
        "/staff/tickets/verify",
    )

    assert response.status_code == 200
    assert "Verify Attendee E-Ticket" in response.text
    assert "E-Ticket Code" in response.text


def test_staff_can_verify_valid_eticket(
    client: TestClient,
    session: Session,
) -> None:
    """A confirmed e-ticket is displayed as valid."""

    _create_user(
        session,
        name="Staff User",
        email="staff@example.com",
        role="staff",
    )

    eticket = _create_eticket(
        session,
    )

    _login(
        client,
        "staff@example.com",
    )

    response = client.get(
        "/staff/tickets/verify",
        params={
            "code": eticket.ticket_code,
        },
    )

    assert response.status_code == 200

    assert "Valid e-ticket" in response.text
    assert eticket.ticket_code in response.text
    assert "Verified Attendee" in response.text
    assert "Verification Concert" in response.text
    assert "National Arena" in response.text
    assert "VIP" in response.text
    assert "Confirmed" in response.text


def test_ticket_verification_is_case_insensitive(
    client: TestClient,
    session: Session,
) -> None:
    """Staff can enter an e-ticket code in lowercase."""

    _create_user(
        session,
        name="Staff User",
        email="staff@example.com",
        role="staff",
    )

    eticket = _create_eticket(
        session,
    )

    _login(
        client,
        "staff@example.com",
    )

    response = client.get(
        "/staff/tickets/verify",
        params={
            "code": eticket.ticket_code.lower(),
        },
    )

    assert response.status_code == 200
    assert "Valid e-ticket" in response.text


def test_invalid_eticket_code_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    """An unknown e-ticket code is displayed as invalid."""

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
        "/staff/tickets/verify",
        params={
            "code": "ET-NOTFOUND123",
        },
    )

    assert response.status_code == 200
    assert "Invalid or unavailable e-ticket" in response.text


def test_unconfirmed_booking_eticket_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    """An e-ticket attached to an unconfirmed booking is invalid."""

    _create_user(
        session,
        name="Staff User",
        email="staff@example.com",
        role="staff",
    )

    eticket = _create_eticket(
        session,
        status="payment_uploaded",
    )

    _login(
        client,
        "staff@example.com",
    )

    response = client.get(
        "/staff/tickets/verify",
        params={
            "code": eticket.ticket_code,
        },
    )

    assert response.status_code == 200
    assert "Invalid or unavailable e-ticket" in response.text


def test_staff_dashboard_links_to_ticket_verification(
    client: TestClient,
    session: Session,
) -> None:
    """The staff dashboard exposes the verification function."""

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
    assert "Verify attendee ticket" in response.text
    assert "/staff/tickets/verify" in response.text
