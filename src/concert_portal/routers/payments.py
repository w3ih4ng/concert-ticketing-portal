from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.services.payments import upload_payment_proof_record
from concert_portal.web import UPLOAD_DIR

router = APIRouter()


@router.post("/bookings/{booking_id}/payment-proof")
def upload_payment_proof(
    booking_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """US24 — Attendee uploads payment proof for a booking."""

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"booking_{booking_id}_{file.filename}"
    (UPLOAD_DIR / filename).write_bytes(file.file.read())

    upload_payment_proof_record(booking_id, filename, session)

    return RedirectResponse(url=f"/bookings/{booking_id}", status_code=303)
