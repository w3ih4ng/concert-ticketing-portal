from fastapi import HTTPException
from sqlmodel import Session

from concert_portal.models import Booking, PaymentProof


def upload_payment_proof_record(booking_id: int, filename: str, session: Session) -> PaymentProof:
    """Persist payment proof for a booking."""

    booking = session.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Cancelled bookings cannot upload payment proof",
        )

    proof = PaymentProof(booking_id=booking_id, filename=filename)
    booking.status = "payment_uploaded"

    session.add(proof)
    session.add(booking)
    session.commit()
    session.refresh(proof)

    return proof
