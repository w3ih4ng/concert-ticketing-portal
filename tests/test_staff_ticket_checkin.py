from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import (
    Booking,
    Concert,
    ETicket,
    Ticket,
    User,
)
from concert_portal.security import password_hash


def _create_staff(
    session: Session,
) -> User:
    """Create a staff account."""

    user = User(
        name="Event Staff",
        email="staff@example.com",
        phone="0123456789",
        role="staff",
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


def _create_attendee(
    session: Session,
) -> User:
    """Create an attendee account."""

    user = User(
        name="Ticket Holder",
        email="attendee@example.com",
        phone="0123456789",
        role="attendee",
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


def _create_confirmed_eticket(
    session: Session,
) -> ETicket:
    """Create a confirmed booking with an e-ticket."""

    concert = Concert(
        title="Check-In Concert",
        date="2030-12-30",
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
        attendee="Ticket Holder",
        quantity=1,
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

    eticket = ETicket(
        booking_id=booking.id,
        ticket_code="ET-CHECKIN12345",
    )

    session.add(
        eticket,
    )
    session.commit()
    session.refresh(
        eticket,
    )

    return eticket


def test_check_in_requires_login(
    client: TestClient,
) -> None:
    """Unauthenticated users cannot check in tickets."""

    response = client.post(
        "/staff/tickets/check-in",
        data={
            "code": "ET-CHECKIN12345",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_non_staff_cannot_check_in_ticket(
    client: TestClient,
    session: Session,
) -> None:
    """Attendees cannot use the staff check-in function."""

    _create_attendee(
        session,
    )

    _login(
        client,
        "attendee@example.com",
    )

    response = client.post(
        "/staff/tickets/check-in",
        data={
            "code": "ET-CHECKIN12345",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_staff_can_check_in_valid_ticket(
    client: TestClient,
    session: Session,
) -> None:
    """Staff can mark a confirmed ticket as checked in."""

    _create_staff(
        session,
    )

    eticket = _create_confirmed_eticket(
        session,
    )

    _login(
        client,
        "staff@example.com",
    )

    response = client.post(
        "/staff/tickets/check-in",
        data={
            "code": eticket.ticket_code,
        },
    )

    assert response.status_code == 200
    assert "Attendee checked in successfully." in response.text
    assert "Already checked in" in response.text

    session.refresh(
        eticket,
    )

    assert eticket.checked_in is True
    assert eticket.checked_in_at is not None


def test_checked_in_ticket_cannot_be_reused(
    client: TestClient,
    session: Session,
) -> None:
    """A checked-in e-ticket cannot be checked in twice."""

    _create_staff(
        session,
    )

    eticket = _create_confirmed_eticket(
        session,
    )

    _login(
        client,
        "staff@example.com",
    )

    first_response = client.post(
        "/staff/tickets/check-in",
        data={
            "code": eticket.ticket_code,
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        "/staff/tickets/check-in",
        data={
            "code": eticket.ticket_code,
        },
    )

    assert second_response.status_code == 409
    assert "This e-ticket has already been checked in." in second_response.text


def test_invalid_ticket_cannot_be_checked_in(
    client: TestClient,
    session: Session,
) -> None:
    """Unknown e-ticket codes are rejected."""

    _create_staff(
        session,
    )

    _login(
        client,
        "staff@example.com",
    )

    response = client.post(
        "/staff/tickets/check-in",
        data={
            "code": "ET-DOESNOTEXIST",
        },
    )

    assert response.status_code == 404
    assert "Valid e-ticket not found." in response.text


def test_verification_shows_not_checked_in(
    client: TestClient,
    session: Session,
) -> None:
    """Unused tickets show the check-in action."""

    _create_staff(
        session,
    )

    eticket = _create_confirmed_eticket(
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
    assert "Not Checked In" in response.text
    assert "Mark as checked in" in response.text


def test_verification_shows_already_checked_in(
    client: TestClient,
    session: Session,
) -> None:
    """Used tickets are clearly shown as already checked in."""

    _create_staff(
        session,
    )

    eticket = _create_confirmed_eticket(
        session,
    )

    eticket.checked_in = True

    session.add(
        eticket,
    )
    session.commit()

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
    assert "Already checked in" in response.text
    assert "cannot be checked in again" in response.text
