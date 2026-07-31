from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from concert_portal.models import Booking, Ticket

FUTURE_DATE = (date.today() + timedelta(days=30)).isoformat()


def _create_booking(
    client: TestClient,
    *,
    ticket_quantity: int = 10,
    booking_quantity: int = 2,
) -> tuple[int, int]:
    concert_response = client.post(
        "/concerts",
        json={
            "title": "Cancellation Test Concert",
            "date": FUTURE_DATE,
            "venue": "City Hall",
            "organiser": "organiser1",
        },
    )

    assert concert_response.status_code == 201
    concert_id = concert_response.json()["id"]

    ticket_response = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": "Standard",
            "price": 50,
            "quantity": ticket_quantity,
        },
    )

    assert ticket_response.status_code == 201
    ticket_id = ticket_response.json()["id"]

    booking_response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "Alyssa",
            "quantity": booking_quantity,
        },
    )

    assert booking_response.status_code == 201
    booking_id = booking_response.json()["id"]

    return booking_id, ticket_id


def test_cancel_pending_booking(client: TestClient) -> None:
    booking_id, _ticket_id = _create_booking(client)

    response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_booking_restores_ticket_stock(
    client: TestClient,
    session: Session,
) -> None:
    booking_id, ticket_id = _create_booking(
        client,
        ticket_quantity=10,
        booking_quantity=3,
    )

    ticket_before = session.get(Ticket, ticket_id)

    assert ticket_before is not None
    assert ticket_before.sold == 3

    response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert response.status_code == 200

    session.expire_all()

    ticket_after = session.get(Ticket, ticket_id)

    assert ticket_after is not None
    assert ticket_after.sold == 0
    assert ticket_after.quantity - ticket_after.sold == 10


def test_cancel_booking_updates_database_status(
    client: TestClient,
    session: Session,
) -> None:
    booking_id, _ticket_id = _create_booking(client)

    response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert response.status_code == 200

    session.expire_all()

    booking = session.get(Booking, booking_id)

    assert booking is not None
    assert booking.status == "cancelled"


def test_cannot_cancel_booking_twice(client: TestClient) -> None:
    booking_id, _ticket_id = _create_booking(client)

    first_response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert second_response.status_code == 409
    assert "already been cancelled" in second_response.json()["detail"]


def test_cannot_cancel_payment_uploaded_booking(
    client: TestClient,
    session: Session,
) -> None:
    booking_id, _ticket_id = _create_booking(client)

    booking = session.get(Booking, booking_id)

    assert booking is not None

    booking.status = "payment_uploaded"
    session.add(booking)
    session.commit()

    response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert response.status_code == 409
    assert "pending payment" in response.json()["detail"]


def test_cancel_missing_booking_returns_404(client: TestClient) -> None:
    response = client.post(
        "/bookings/999/cancel",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"


def test_booking_detail_shows_cancel_button_for_pending_booking(
    client: TestClient,
) -> None:
    booking_id, _ticket_id = _create_booking(client)

    response = client.get(
        f"/bookings/{booking_id}",
    )

    assert response.status_code == 200
    assert "Cancel booking" in response.text
    assert "Are you sure you want to cancel this booking?" in response.text


def test_booking_detail_hides_cancel_button_after_cancellation(
    client: TestClient,
) -> None:
    booking_id, _ticket_id = _create_booking(client)

    cancel_response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert cancel_response.status_code == 200

    response = client.get(
        f"/bookings/{booking_id}",
    )

    assert response.status_code == 200
    assert "This booking has been cancelled." in response.text
    assert ">Cancel booking<" not in response.text


def test_cancel_booking_form_redirects_with_success_message(
    client: TestClient,
) -> None:
    booking_id, _ticket_id = _create_booking(client)

    response = client.post(
        f"/bookings/{booking_id}/cancel/form",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/bookings/{booking_id}?message=cancelled")

    followed = client.get(response.headers["location"])

    assert followed.status_code == 200
    assert "Booking cancelled successfully" in followed.text
    assert "cancelled" in followed.text


def test_cancel_booking_form_rejects_second_cancellation(
    client: TestClient,
) -> None:
    booking_id, _ticket_id = _create_booking(client)

    first_response = client.post(
        f"/bookings/{booking_id}/cancel/form",
        follow_redirects=False,
    )

    assert first_response.status_code == 303

    second_response = client.post(
        f"/bookings/{booking_id}/cancel/form",
        follow_redirects=False,
    )

    assert second_response.status_code == 303
    assert second_response.headers["location"] == (
        f"/bookings/{booking_id}?error=already_cancelled"
    )


def test_cancelled_booking_cannot_upload_payment_proof(
    client: TestClient,
) -> None:
    booking_id, _ticket_id = _create_booking(client)

    cancel_response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert cancel_response.status_code == 200

    upload_response = client.post(
        f"/bookings/{booking_id}/payment-proof",
        files={
            "file": (
                "receipt.png",
                b"fake image data",
                "image/png",
            )
        },
    )

    assert upload_response.status_code == 409
    assert "Cancelled bookings" in upload_response.json()["detail"]


def test_cancelling_one_booking_does_not_change_other_bookings(
    client: TestClient,
    session: Session,
) -> None:
    booking_id, ticket_id = _create_booking(
        client,
        ticket_quantity=10,
        booking_quantity=2,
    )

    second_booking_response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "Second Attendee",
            "quantity": 3,
        },
    )

    assert second_booking_response.status_code == 201

    cancel_response = client.post(
        f"/bookings/{booking_id}/cancel",
    )

    assert cancel_response.status_code == 200

    session.expire_all()

    ticket = session.get(Ticket, ticket_id)

    assert ticket is not None
    assert ticket.sold == 3

    bookings = session.exec(select(Booking)).all()

    assert len(bookings) == 2

    statuses = {booking.attendee: booking.status for booking in bookings}

    assert statuses["Alyssa"] == "cancelled"
    assert statuses["Second Attendee"] == "pending_payment"
