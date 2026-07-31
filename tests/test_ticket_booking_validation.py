from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from concert_portal.models import Booking, Ticket

FUTURE_DATE = (date.today() + timedelta(days=30)).isoformat()


def _create_concert(client: TestClient) -> int:
    response = client.post(
        "/concerts",
        json={
            "title": "Rock Night",
            "date": FUTURE_DATE,
            "venue": "National Stadium",
            "organiser": "organiser1",
        },
    )

    assert response.status_code == 201

    concert_id: int = response.json()["id"]
    return concert_id


def _create_ticket(
    client: TestClient,
    *,
    concert_id: int,
    category: str = "VIP",
    price: float = 150.0,
    quantity: int | float = 10,
) -> int:
    response = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": category,
            "price": price,
            "quantity": quantity,
        },
    )

    assert response.status_code == 201

    ticket_id: int = response.json()["id"]
    return ticket_id


# ---------- Ticket API ----------


def test_ticket_api_rejects_blank_category(client: TestClient) -> None:
    concert_id = _create_concert(client)

    response = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": "   ",
            "price": 50,
            "quantity": 10,
        },
    )

    assert response.status_code == 422
    assert "category" in response.json()["detail"]


def test_ticket_api_rejects_negative_price(client: TestClient) -> None:
    concert_id = _create_concert(client)

    response = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": "VIP",
            "price": -1,
            "quantity": 10,
        },
    )

    assert response.status_code == 422
    assert "price" in response.json()["detail"]


def test_ticket_api_rejects_zero_quantity(client: TestClient) -> None:
    concert_id = _create_concert(client)

    response = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": "VIP",
            "price": 50,
            "quantity": 0,
        },
    )

    assert response.status_code == 422
    assert "quantity" in response.json()["detail"]


def test_ticket_api_rejects_decimal_quantity(client: TestClient) -> None:
    concert_id = _create_concert(client)

    response = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": "VIP",
            "price": 50,
            "quantity": 1.5,
        },
    )

    assert response.status_code == 422


def test_ticket_api_trims_category(client: TestClient) -> None:
    concert_id = _create_concert(client)

    response = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": "  VIP  ",
            "price": 50,
            "quantity": 10,
        },
    )

    assert response.status_code == 201
    assert response.json()["category"] == "VIP"


# ---------- Ticket HTML form ----------


def test_ticket_form_preserves_values_on_error(client: TestClient) -> None:
    concert_id = _create_concert(client)

    response = client.post(
        f"/concerts/{concert_id}/tickets/new",
        data={
            "category": "VIP",
            "price": "-20",
            "quantity": "10",
        },
    )

    assert response.status_code == 422
    assert "Ticket price cannot be negative." in response.text
    assert 'value="VIP"' in response.text
    assert 'value="10"' in response.text


def test_ticket_form_rejects_decimal_quantity(client: TestClient) -> None:
    concert_id = _create_concert(client)

    response = client.post(
        f"/concerts/{concert_id}/tickets/new",
        data={
            "category": "VIP",
            "price": "50",
            "quantity": "2.5",
        },
    )

    assert response.status_code == 422
    assert "Ticket quantity must be a whole number." in response.text


# ---------- Booking API ----------


def test_booking_api_rejects_blank_attendee(client: TestClient) -> None:
    concert_id = _create_concert(client)
    ticket_id = _create_ticket(client, concert_id=concert_id)

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "   ",
            "quantity": 1,
        },
    )

    assert response.status_code == 422
    assert "attendee" in response.json()["detail"]


def test_booking_api_rejects_zero_quantity(client: TestClient) -> None:
    concert_id = _create_concert(client)
    ticket_id = _create_ticket(client, concert_id=concert_id)

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "Alyssa",
            "quantity": 0,
        },
    )

    assert response.status_code == 400
    assert "quantity" in response.json()["detail"]


def test_booking_api_rejects_quantity_above_stock(
    client: TestClient,
) -> None:
    concert_id = _create_concert(client)
    ticket_id = _create_ticket(
        client,
        concert_id=concert_id,
        quantity=2,
    )

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "Alyssa",
            "quantity": 3,
        },
    )

    assert response.status_code == 409
    assert "remaining" in response.json()["detail"]


def test_booking_api_trims_attendee_name(client: TestClient) -> None:
    concert_id = _create_concert(client)
    ticket_id = _create_ticket(client, concert_id=concert_id)

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "  Alyssa  ",
            "quantity": 1,
        },
    )

    assert response.status_code == 201
    assert response.json()["attendee"] == "Alyssa"


def test_booking_never_makes_ticket_stock_negative(
    client: TestClient,
    session: Session,
) -> None:
    concert_id = _create_concert(client)
    ticket_id = _create_ticket(
        client,
        concert_id=concert_id,
        quantity=2,
    )

    first_response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "Alyssa",
            "quantity": 2,
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket_id,
            "attendee": "Another Attendee",
            "quantity": 1,
        },
    )

    assert second_response.status_code == 409

    ticket = session.get(Ticket, ticket_id)
    assert ticket is not None
    assert ticket.sold == 2
    assert ticket.quantity - ticket.sold == 0

    bookings = session.exec(select(Booking)).all()
    assert len(bookings) == 1


# ---------- Booking HTML form ----------


def test_booking_form_redirects_blank_attendee_with_error(
    client: TestClient,
) -> None:
    concert_id = _create_concert(client)
    ticket_id = _create_ticket(client, concert_id=concert_id)

    response = client.post(
        "/bookings/new",
        data={
            "ticket_id": str(ticket_id),
            "attendee": "   ",
            "quantity": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "error=blank_attendee" in response.headers["location"]


def test_booking_form_rejects_decimal_quantity(
    client: TestClient,
) -> None:
    concert_id = _create_concert(client)
    ticket_id = _create_ticket(client, concert_id=concert_id)

    response = client.post(
        "/bookings/new",
        data={
            "ticket_id": str(ticket_id),
            "attendee": "Alyssa",
            "quantity": "1.5",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "error=bad_quantity" in response.headers["location"]
