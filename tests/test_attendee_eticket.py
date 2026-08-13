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
    role: str = "attendee",
) -> User:
    """Create a user for e-ticket tests."""

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
    user: User,
    *,
    status: str = "confirmed",
    code: str = "ET-TEST12345678",
) -> tuple[Booking, ETicket]:
    """Create a concert booking and generated e-ticket."""

    assert user.id is not None

    concert = Concert(
        title="E-Ticket Live",
        date="2030-12-20",
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
        price=150.00,
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
        attendee=user.name,
        quantity=2,
        user_id=user.id,
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

    return booking, eticket


def test_eticket_requires_login(
    client: TestClient,
    session: Session,
) -> None:
    """Unauthenticated users are redirected to login."""

    attendee = _create_user(
        session,
        name="Ticket Owner",
        email="owner@example.com",
    )

    booking, _ = _create_eticket(
        session,
        attendee,
    )

    assert booking.id is not None

    response = client.get(
        f"/bookings/{booking.id}/eticket",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_attendee_can_view_own_eticket(
    client: TestClient,
    session: Session,
) -> None:
    """An attendee can view their confirmed e-ticket."""

    attendee = _create_user(
        session,
        name="Ticket Owner",
        email="owner@example.com",
    )

    booking, eticket = _create_eticket(
        session,
        attendee,
    )

    assert booking.id is not None

    _login(
        client,
        "owner@example.com",
    )

    response = client.get(
        f"/bookings/{booking.id}/eticket",
    )

    assert response.status_code == 200

    assert eticket.ticket_code in response.text
    assert "Ticket Owner" in response.text
    assert "E-Ticket Live" in response.text
    assert "2030-12-20" in response.text
    assert "National Arena" in response.text
    assert "VIP" in response.text
    assert "Valid confirmed e-ticket" in response.text


def test_attendee_cannot_view_another_attendees_eticket(
    client: TestClient,
    session: Session,
) -> None:
    """An attendee cannot access another attendee's e-ticket."""

    owner = _create_user(
        session,
        name="Ticket Owner",
        email="owner@example.com",
    )

    _create_user(
        session,
        name="Other Attendee",
        email="other@example.com",
    )

    booking, _ = _create_eticket(
        session,
        owner,
    )

    assert booking.id is not None

    _login(
        client,
        "other@example.com",
    )

    response = client.get(
        f"/bookings/{booking.id}/eticket",
    )

    assert response.status_code == 404


def test_non_attendee_cannot_view_eticket(
    client: TestClient,
    session: Session,
) -> None:
    """Non-attendee roles cannot access attendee e-tickets."""

    attendee = _create_user(
        session,
        name="Ticket Owner",
        email="owner@example.com",
    )

    admin = _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    booking, _ = _create_eticket(
        session,
        attendee,
    )

    assert booking.id is not None
    assert admin.id is not None

    _login(
        client,
        "admin@example.com",
    )

    response = client.get(
        f"/bookings/{booking.id}/eticket",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard"


def test_unconfirmed_booking_cannot_view_eticket(
    client: TestClient,
    session: Session,
) -> None:
    """An e-ticket is unavailable before booking confirmation."""

    attendee = _create_user(
        session,
        name="Ticket Owner",
        email="owner@example.com",
    )

    booking, _ = _create_eticket(
        session,
        attendee,
        status="payment_uploaded",
    )

    assert booking.id is not None

    _login(
        client,
        "owner@example.com",
    )

    response = client.get(
        f"/bookings/{booking.id}/eticket",
    )

    assert response.status_code == 404


def test_missing_eticket_returns_404(
    client: TestClient,
    session: Session,
) -> None:
    """A confirmed booking without an e-ticket returns 404."""

    attendee = _create_user(
        session,
        name="Ticket Owner",
        email="owner@example.com",
    )

    assert attendee.id is not None

    concert = Concert(
        title="Missing Ticket Concert",
        date="2030-12-21",
        venue="Arena",
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
        category="Standard",
        price=50.00,
        quantity=50,
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
        attendee=attendee.name,
        quantity=1,
        user_id=attendee.id,
        status="confirmed",
    )

    session.add(
        booking,
    )
    session.commit()
    session.refresh(
        booking,
    )

    assert booking.id is not None

    _login(
        client,
        "owner@example.com",
    )

    response = client.get(
        f"/bookings/{booking.id}/eticket",
    )

    assert response.status_code == 404


def test_confirmed_booking_history_shows_eticket_link(
    client: TestClient,
    session: Session,
) -> None:
    """Confirmed attendee bookings expose the e-ticket action."""

    attendee = _create_user(
        session,
        name="Ticket Owner",
        email="owner@example.com",
    )

    booking, _ = _create_eticket(
        session,
        attendee,
    )

    assert booking.id is not None

    _login(
        client,
        "owner@example.com",
    )

    response = client.get(
        "/bookings/history",
    )

    assert response.status_code == 200
    assert "View e-ticket" in response.text
    assert f"/bookings/{booking.id}/eticket" in response.text
