import io

from fastapi.testclient import TestClient


def _create_booking(client: TestClient) -> int:
    """Helper: create concert + ticket + booking, return the booking id."""
    concert = client.post(
        "/concerts",
        json={
            "title": "Rock Night",
            "date": "2026-08-01",
            "venue": "National Stadium",
            "organiser": "organiser1",
        },
    )
    ticket = client.post(
        "/tickets",
        json={
            "concert_id": concert.json()["id"],
            "category": "VIP",
            "price": 250.0,
            "quantity": 10,
        },
    )
    booking = client.post(
        "/bookings",
        json={"ticket_id": ticket.json()["id"], "attendee": "attendee1", "quantity": 2},
    )
    assert booking.status_code == 201
    booking_id: int = booking.json()["id"]
    return booking_id


def test_upload_payment_proof(client: TestClient) -> None:
    """
    US24 — Upload payment proof
      When an attendee uploads proof for their booking
      Then it is saved and the booking status changes
    """
    booking_id = _create_booking(client)

    response = client.post(
        f"/bookings/{booking_id}/payment-proof",
        files={"file": ("receipt.png", io.BytesIO(b"fake image bytes"), "image/png")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "payment_uploaded" in response.text
    assert "receipt.png" in response.text


def test_upload_proof_for_missing_booking(client: TestClient) -> None:
    """Uploading proof for a non-existent booking returns 404."""
    response = client.post(
        "/bookings/999/payment-proof",
        files={"file": ("receipt.png", io.BytesIO(b"data"), "image/png")},
    )
    assert response.status_code == 404