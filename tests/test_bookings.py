from fastapi.testclient import TestClient


def _create_ticket(client: TestClient, quantity: int = 10) -> int:
    """Helper: create a concert + ticket, return the ticket id."""
    concert = client.post(
        "/concerts",
        json={
            "title": "Rock Night",
            "date": "2026-08-01",
            "venue": "National Stadium",
            "organiser": "organiser1",
        },
    )
    concert_id = concert.json()["id"]

    ticket = client.post(
        "/tickets",
        json={
            "concert_id": concert_id,
            "category": "VIP",
            "price": 250.0,
            "quantity": quantity,
        },
    )
    assert ticket.status_code == 201
    ticket_id: int = ticket.json()["id"]
    return ticket_id


def test_create_booking(client: TestClient) -> None:
    """
    US20/21 — Select tickets and create a booking
      When an attendee books 2 of an available ticket
      Then the booking is created (201) as pending payment
    """
    ticket_id = _create_ticket(client, quantity=10)

    response = client.post(
        "/bookings",
        json={"ticket_id": ticket_id, "attendee": "attendee1", "quantity": 2},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 2
    assert body["status"] == "pending_payment"
    assert isinstance(body["id"], int)


def test_booking_updates_sold_count(client: TestClient) -> None:
    """A successful booking increases the ticket's sold count."""
    ticket_id = _create_ticket(client, quantity=10)

    client.post(
        "/bookings",
        json={"ticket_id": ticket_id, "attendee": "attendee1", "quantity": 3},
    )

    concert_id = 1
    tickets = client.get(f"/concerts/{concert_id}/tickets").json()
    assert tickets[0]["sold"] == 3


def test_cannot_oversell(client: TestClient) -> None:
    """
    US19 — Prevent ticket overselling
      Given only 5 tickets exist
      When an attendee tries to book 6
      Then the booking is rejected (409)
    """
    ticket_id = _create_ticket(client, quantity=5)

    response = client.post(
        "/bookings",
        json={"ticket_id": ticket_id, "attendee": "attendee1", "quantity": 6},
    )
    assert response.status_code == 409
    assert "remaining" in response.json()["detail"]


def test_cannot_oversell_across_multiple_bookings(client: TestClient) -> None:
    """
    US19 — Overselling is prevented cumulatively, not just per request
      Given 5 tickets and 4 already booked
      When another attendee tries to book 2
      Then the booking is rejected (409)
    """
    ticket_id = _create_ticket(client, quantity=5)

    first = client.post(
        "/bookings",
        json={"ticket_id": ticket_id, "attendee": "attendee1", "quantity": 4},
    )
    assert first.status_code == 201

    second = client.post(
        "/bookings",
        json={"ticket_id": ticket_id, "attendee": "attendee2", "quantity": 2},
    )
    assert second.status_code == 409


def test_booking_missing_ticket(client: TestClient) -> None:
    """Booking a non-existent ticket returns 404."""
    response = client.post(
        "/bookings",
        json={"ticket_id": 999, "attendee": "attendee1", "quantity": 1},
    )
    assert response.status_code == 404


def test_booking_zero_quantity(client: TestClient) -> None:
    """Booking zero tickets is rejected."""
    ticket_id = _create_ticket(client)

    response = client.post(
        "/bookings",
        json={"ticket_id": ticket_id, "attendee": "attendee1", "quantity": 0},
    )
    assert response.status_code == 400
