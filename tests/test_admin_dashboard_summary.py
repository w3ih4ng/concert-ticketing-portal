import re

from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import (
    Booking,
    Concert,
    ConcertApproval,
    ETicket,
    OrganiserProfile,
    PaymentProof,
    Ticket,
    User,
)
from concert_portal.security import password_hash


def _visible_text(html: str) -> str:
    """Return normalized visible text from rendered HTML."""

    without_tags = re.sub(
        r"<[^>]+>",
        " ",
        html,
    )

    return " ".join(without_tags.split())


def _create_user(
    session: Session,
    *,
    name: str,
    email: str,
    role: str,
) -> User:
    """Create a test user."""

    user = User(
        name=name,
        email=email,
        phone="012-3456789",
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


def _login_admin(
    client: TestClient,
) -> None:
    """Login using the test administrator account."""

    response = client.post(
        "/login",
        data={
            "email": "admin@example.com",
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard"


def test_admin_dashboard_requires_login(
    client: TestClient,
) -> None:
    """Unauthenticated users cannot access the admin dashboard."""

    response = client.get(
        "/admin/dashboard",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_dashboard_shows_zero_summary(
    client: TestClient,
    session: Session,
) -> None:
    """The dashboard displays summary values when no activity exists."""

    _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    _login_admin(
        client,
    )

    response = client.get(
        "/admin/dashboard",
    )

    assert response.status_code == 200

    assert "Dashboard Summary" in response.text
    assert "Total registered users" in response.text
    assert "Total concert records" in response.text
    assert "Total ticket bookings" in response.text
    assert "Total payments" in response.text
    assert "Total attendee check-ins" in response.text
    assert "Pending organiser approvals" in response.text
    assert "Concerts awaiting approval" in response.text
    assert "Payments awaiting verification" in response.text


def test_admin_dashboard_counts_users_concerts_and_bookings(
    client: TestClient,
    session: Session,
) -> None:
    """The dashboard counts core portal records."""

    _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    _create_user(
        session,
        name="Attendee User",
        email="attendee@example.com",
        role="attendee",
    )

    concert = Concert(
        title="Summary Concert",
        date="2030-08-01",
        venue="National Stadium",
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
        price=100.00,
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
        attendee="Attendee User",
        quantity=2,
        status="pending_payment",
    )

    session.add(
        booking,
    )
    session.commit()

    _login_admin(
        client,
    )

    response = client.get(
        "/admin/dashboard",
    )

    assert response.status_code == 200

    assert "Total registered users" in response.text
    assert "Total concert records" in response.text
    assert "Total ticket bookings" in response.text

    assert ">2<" in response.text.replace(
        "\n",
        "",
    ).replace(
        " ",
        "",
    )

    assert ">1<" in response.text.replace(
        "\n",
        "",
    ).replace(
        " ",
        "",
    )


def test_admin_dashboard_counts_pending_items(
    client: TestClient,
    session: Session,
) -> None:
    """Pending organiser, concert and payment work appears in summary."""

    admin = _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    organiser = _create_user(
        session,
        name="Organiser User",
        email="organiser@example.com",
        role="organiser",
    )

    assert admin.id is not None
    assert organiser.id is not None

    profile = OrganiserProfile(
        user_id=organiser.id,
        organisation_name="Test Events",
        registration_number="REG-100",
        organisation_address="Test Address",
        status="pending",
    )

    concert = Concert(
        title="Pending Concert",
        date="2030-09-01",
        venue="Arena",
        organiser="Test Events",
    )

    session.add(
        profile,
    )
    session.add(
        concert,
    )
    session.commit()
    session.refresh(
        concert,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="pending",
    )

    ticket = Ticket(
        concert_id=concert.id,
        category="VIP",
        price=200.00,
        quantity=20,
    )

    session.add(
        approval,
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
        attendee="Test Attendee",
        quantity=1,
        status="payment_uploaded",
    )

    session.add(
        booking,
    )
    session.commit()

    _login_admin(
        client,
    )

    response = client.get(
        "/admin/dashboard",
    )

    assert response.status_code == 200

    visible_text = _visible_text(
        response.text,
    )

    assert "1 concert" in visible_text
    assert "1 organiser account" in visible_text
    assert "1 payment" in visible_text


def test_confirmed_payment_not_counted_as_pending(
    client: TestClient,
    session: Session,
) -> None:
    """Confirmed bookings must not count as pending payment verification."""

    _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    concert = Concert(
        title="Confirmed Concert",
        date="2030-10-01",
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
        quantity=10,
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
        attendee="Confirmed Attendee",
        quantity=1,
        status="confirmed",
    )

    session.add(
        booking,
    )
    session.commit()

    _login_admin(
        client,
    )

    response = client.get(
        "/admin/dashboard",
    )

    assert response.status_code == 200
    visible_text = _visible_text(
        response.text,
    )

    assert "0 payments awaiting verification" in visible_text


def test_admin_dashboard_counts_payments_and_checkins(
    client: TestClient,
    session: Session,
) -> None:
    """The dashboard counts payment records and completed check-ins."""

    _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    concert = Concert(
        title="Dashboard Statistics Concert",
        date="2030-11-01",
        venue="Main Arena",
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
        price=80.00,
        quantity=20,
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
        attendee="Checked In Attendee",
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

    proof = PaymentProof(
        booking_id=booking.id,
        filename="payment-proof.jpg",
    )

    eticket = ETicket(
        booking_id=booking.id,
        ticket_code="TEST-CHECKIN-001",
        checked_in=True,
    )

    session.add(
        proof,
    )
    session.add(
        eticket,
    )
    session.commit()

    _login_admin(
        client,
    )

    response = client.get(
        "/admin/dashboard",
    )

    assert response.status_code == 200

    visible_text = _visible_text(
        response.text,
    )

    assert "Total payments" in visible_text
    assert "Total attendee check-ins" in visible_text
