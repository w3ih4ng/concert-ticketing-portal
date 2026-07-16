from fastapi.testclient import TestClient


def _create_ticket(client: TestClient, quantity: int = 10) -> tuple[int, int]:
    """Helper: create a concert + ticket, return (concert_id, ticket_id)."""
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
    return concert_id, ticket_id


def test_booking_form_redirects_to_confirmation(client: TestClient) -> None:
    """A successful form booking redirects (303) straight to /bookings/{id}."""
    _concert_id, ticket_id = _create_ticket(client)

    response = client.post(
        "/bookings/new",
        data={"ticket_id": str(ticket_id), "attendee": "Alex", "quantity": "2"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/bookings/")

    followed = client.get(response.headers["location"])
    assert followed.status_code == 200
    assert "Booking Confirmed" in followed.text
    assert "Alex" in followed.text


def test_oversold_booking_form_redirects_with_error_banner(client: TestClient) -> None:
    """
    Overbooking through the HTML form must not dead-end in raw JSON —
    it should redirect (303) back to the concert page with a friendly banner.
    """
    concert_id, ticket_id = _create_ticket(client, quantity=5)

    response = client.post(
        "/bookings/new",
        data={"ticket_id": str(ticket_id), "attendee": "Alex", "quantity": "6"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/concerts/{concert_id}?error=oversold"

    followed = client.get(response.headers["location"])
    assert followed.status_code == 200
    assert followed.headers["content-type"].startswith("text/html")
    assert "Not enough tickets left" in followed.text


def test_bad_quantity_booking_form_redirects_with_error_banner(client: TestClient) -> None:
    """Booking zero tickets through the form redirects with a bad_quantity banner."""
    concert_id, ticket_id = _create_ticket(client)

    response = client.post(
        "/bookings/new",
        data={"ticket_id": str(ticket_id), "attendee": "Alex", "quantity": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/concerts/{concert_id}?error=bad_quantity"

    followed = client.get(response.headers["location"])
    assert "Quantity must be at least 1" in followed.text


def test_unknown_ticket_booking_form_redirects_home_with_error(client: TestClient) -> None:
    """Booking a non-existent ticket through the form redirects home with an error banner."""
    response = client.post(
        "/bookings/new",
        data={"ticket_id": "999", "attendee": "Alex", "quantity": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/?error=not_found"

    followed = client.get(response.headers["location"])
    assert "That ticket could not be found" in followed.text
