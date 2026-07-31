import io

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from concert_portal.models import (
    Booking,
    Concert,
    PaymentProof,
    Ticket,
)


def _create_booking(session: Session) -> Booking:
    """Create a pending booking directly in the test database."""

    concert = Concert(
        title="Payment Test Concert",
        date="2027-12-10",
        venue="National Stadium",
        organiser="Live Events",
    )

    session.add(concert)
    session.commit()
    session.refresh(concert)

    assert concert.id is not None

    ticket = Ticket(
        concert_id=concert.id,
        category="General",
        price=80.00,
        quantity=100,
        sold=1,
    )

    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    assert ticket.id is not None

    booking = Booking(
        ticket_id=ticket.id,
        attendee="Test Attendee",
        quantity=1,
        status="pending_payment",
    )

    session.add(booking)
    session.commit()
    session.refresh(booking)

    assert booking.id is not None

    return booking


def test_upload_payment_proof(
    client: TestClient,
    session: Session,
) -> None:
    """
    US24 — Upload payment proof.

    A valid proof is stored securely and the booking is marked
    as waiting for admin review.
    """

    booking = _create_booking(session)

    assert booking.id is not None

    response = client.post(
        f"/bookings/{booking.id}/payment-proof",
        files={
            "file": (
                "receipt.png",
                io.BytesIO(b"\x89PNG\r\n\x1a\n" b"valid test payment proof"),
                "image/png",
            )
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Payment Uploaded" in response.text
    assert "Payment proof uploaded. It is waiting for admin review." in response.text

    session.refresh(booking)

    assert booking.status == "payment_uploaded"

    proof = session.exec(select(PaymentProof).where(PaymentProof.booking_id == booking.id)).first()

    assert proof is not None
    assert proof.filename.startswith(f"booking_{booking.id}_")
    assert proof.filename.endswith(".png")
    assert proof.filename != "receipt.png"
