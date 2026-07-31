from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlmodel import Session, select

from concert_portal.models import Booking, Concert, Ticket, User

password_hash = PasswordHash.recommended()


def _create_user(
    session: Session,
    *,
    name: str,
    email: str,
    role: str = "attendee",
) -> User:
    user = User(
        name=name,
        email=email,
        phone="012-3456789",
        role=role,
        password_hash=password_hash.hash("Password123"),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


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


def _create_ticket(
    session: Session,
    *,
    title: str = "Summer Concert",
) -> Ticket:
    concert = Concert(
        title=title,
        date="2027-01-20",
        venue="National Stadium",
        organiser="Live Events",
    )

    session.add(concert)
    session.commit()
    session.refresh(concert)

    assert concert.id is not None

    ticket = Ticket(
        concert_id=concert.id,
        category="VIP",
        price=120.00,
        quantity=100,
        sold=0,
    )

    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    return ticket


def test_booking_history_requires_login(
    client: TestClient,
) -> None:
    response = client.get(
        "/bookings/history",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_empty_booking_history_is_displayed(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        name="Alyssa Loh",
        email="alyssa@example.com",
    )

    _login(
        client,
        email="alyssa@example.com",
    )

    response = client.get("/bookings/history")

    assert response.status_code == 200
    assert "My Booking History" in response.text
    assert "No bookings yet" in response.text


def test_history_only_displays_current_attendee_bookings(
    client: TestClient,
    session: Session,
) -> None:
    alyssa = _create_user(
        session,
        name="Alyssa Loh",
        email="alyssa@example.com",
    )
    another_user = _create_user(
        session,
        name="Another User",
        email="another@example.com",
    )
    ticket = _create_ticket(session)

    assert alyssa.id is not None
    assert another_user.id is not None
    assert ticket.id is not None

    own_booking = Booking(
        ticket_id=ticket.id,
        attendee="Alyssa Loh",
        quantity=2,
        user_id=alyssa.id,
        status="pending_payment",
    )
    other_booking = Booking(
        ticket_id=ticket.id,
        attendee="Another User",
        quantity=1,
        user_id=another_user.id,
        status="confirmed",
    )

    session.add(own_booking)
    session.add(other_booking)
    session.commit()
    session.refresh(own_booking)
    session.refresh(other_booking)

    _login(
        client,
        email="alyssa@example.com",
    )

    response = client.get("/bookings/history")

    assert response.status_code == 200
    assert f"Booking #{own_booking.id}" in response.text
    assert f"Booking #{other_booking.id}" not in response.text


def test_history_displays_booking_status_and_detail_link(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        name="Alyssa Loh",
        email="alyssa@example.com",
    )
    ticket = _create_ticket(
        session,
        title="Rock Festival",
    )

    assert user.id is not None
    assert ticket.id is not None

    booking = Booking(
        ticket_id=ticket.id,
        attendee=user.name,
        quantity=2,
        user_id=user.id,
        status="payment_uploaded",
    )

    session.add(booking)
    session.commit()
    session.refresh(booking)

    _login(
        client,
        email="alyssa@example.com",
    )

    response = client.get("/bookings/history")

    assert response.status_code == 200
    assert "Rock Festival" in response.text
    assert "Payment Uploaded" in response.text
    assert "VIP" in response.text
    assert "RM 240.00" in response.text
    assert f'href="/bookings/{booking.id}"' in response.text


def test_history_displays_newest_booking_first(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        name="Alyssa Loh",
        email="alyssa@example.com",
    )
    first_ticket = _create_ticket(
        session,
        title="First Concert",
    )
    second_ticket = _create_ticket(
        session,
        title="Second Concert",
    )

    assert user.id is not None
    assert first_ticket.id is not None
    assert second_ticket.id is not None

    first_booking = Booking(
        ticket_id=first_ticket.id,
        attendee=user.name,
        quantity=1,
        user_id=user.id,
    )
    second_booking = Booking(
        ticket_id=second_ticket.id,
        attendee=user.name,
        quantity=1,
        user_id=user.id,
    )

    session.add(first_booking)
    session.commit()
    session.add(second_booking)
    session.commit()

    _login(
        client,
        email="alyssa@example.com",
    )

    response = client.get("/bookings/history")

    assert response.status_code == 200
    assert response.text.index("Second Concert") < response.text.index("First Concert")


def test_logged_in_booking_is_linked_to_attendee_account(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        name="Alyssa Loh",
        email="alyssa@example.com",
    )
    ticket = _create_ticket(session)

    assert user.id is not None
    assert ticket.id is not None

    _login(
        client,
        email="alyssa@example.com",
    )

    response = client.post(
        "/bookings/new",
        data={
            "ticket_id": str(ticket.id),
            "attendee": "Alyssa Loh",
            "quantity": "2",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    booking = session.exec(select(Booking).where(Booking.user_id == user.id)).first()

    assert booking is not None
    assert booking.user_id == user.id


def test_logged_in_booking_uses_registered_user_name(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(
        session,
        name="Alyssa Loh",
        email="alyssa@example.com",
    )
    ticket = _create_ticket(session)

    assert user.id is not None
    assert ticket.id is not None

    _login(
        client,
        email="alyssa@example.com",
    )

    response = client.post(
        "/bookings/new",
        data={
            "ticket_id": str(ticket.id),
            "attendee": "Someone Else",
            "quantity": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    booking = session.exec(select(Booking).where(Booking.user_id == user.id)).first()

    assert booking is not None
    assert booking.attendee == "Alyssa Loh"


def test_api_booking_remains_backward_compatible(
    client: TestClient,
    session: Session,
) -> None:
    ticket = _create_ticket(session)

    assert ticket.id is not None

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket.id,
            "attendee": "Guest Attendee",
            "quantity": 1,
        },
    )

    assert response.status_code == 201

    booking_id = response.json()["id"]
    booking = session.get(Booking, booking_id)

    assert booking is not None
    assert booking.user_id is None


def test_non_attendee_is_redirected_from_booking_history(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        name="Admin User",
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get(
        "/bookings/history",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard"
