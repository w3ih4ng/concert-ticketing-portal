from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from concert_portal.models import Booking, PaymentProof

MAX_PAYMENT_PROOF_SIZE = 5 * 1024 * 1024

ALLOWED_PAYMENT_PROOF_TYPES = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
    ".pdf": {"application/pdf"},
}


def get_booking_for_payment_upload(
    booking_id: int,
    session: Session,
) -> Booking:
    """Return a booking that is allowed to receive payment proof."""

    booking = session.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found.",
        )

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Cancelled bookings cannot upload payment proof.",
        )

    if booking.status == "confirmed":
        raise HTTPException(
            status_code=409,
            detail="This booking has already been confirmed.",
        )

    existing_proof = session.exec(
        select(PaymentProof).where(PaymentProof.booking_id == booking_id)
    ).first()

    if existing_proof is not None:
        raise HTTPException(
            status_code=409,
            detail=("A payment proof has already been submitted " "for this booking."),
        )

    return booking


def validate_payment_proof(
    *,
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> str:
    """Validate filename extension, MIME type, size and signature."""

    if filename is None or not filename.strip():
        raise HTTPException(
            status_code=422,
            detail="Select a payment proof file to upload.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_PAYMENT_PROOF_TYPES:
        raise HTTPException(
            status_code=422,
            detail=("Payment proof must be a JPG, JPEG, PNG or PDF file."),
        )

    allowed_content_types = ALLOWED_PAYMENT_PROOF_TYPES[extension]

    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=422,
            detail=("The uploaded file type does not match " "its filename extension."),
        )

    if not content:
        raise HTTPException(
            status_code=422,
            detail="The uploaded payment proof file is empty.",
        )

    if len(content) > MAX_PAYMENT_PROOF_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Payment proof files must not exceed 5 MB.",
        )

    if extension in {".jpg", ".jpeg"}:
        valid_signature = content.startswith(b"\xff\xd8\xff")
    elif extension == ".png":
        valid_signature = content.startswith(b"\x89PNG\r\n\x1a\n")
    else:
        valid_signature = content.startswith(b"%PDF-")

    if not valid_signature:
        file_type = extension.removeprefix(".").upper()

        raise HTTPException(
            status_code=422,
            detail=("The uploaded file content is not " f"a valid {file_type} file."),
        )

    return extension


def generate_payment_proof_filename(
    booking_id: int,
    extension: str,
) -> str:
    """Generate a safe server-controlled filename."""

    return f"booking_{booking_id}_" f"{uuid4().hex}" f"{extension}"


def save_payment_proof_record(
    booking: Booking,
    stored_filename: str,
    session: Session,
) -> PaymentProof:
    """Save payment metadata and mark the booking for admin review."""

    if booking.id is None:
        raise HTTPException(
            status_code=500,
            detail="Booking could not be updated.",
        )

    existing_proof = session.exec(
        select(PaymentProof).where(PaymentProof.booking_id == booking.id)
    ).first()

    if existing_proof is not None:
        raise HTTPException(
            status_code=409,
            detail=("A payment proof has already been submitted " "for this booking."),
        )

    proof = PaymentProof(
        booking_id=booking.id,
        filename=stored_filename,
    )

    booking.status = "payment_uploaded"

    session.add(proof)
    session.add(booking)
    session.commit()
    session.refresh(proof)

    return proof
