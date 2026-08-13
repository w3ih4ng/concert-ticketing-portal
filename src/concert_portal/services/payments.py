from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, col, select

from concert_portal.models import (
    Booking,
    Concert,
    PaymentProof,
    Ticket,
)
from concert_portal.services.etickets import generate_eticket
from concert_portal.web import UPLOAD_DIR

MAX_PAYMENT_PROOF_SIZE = 5 * 1024 * 1024

ALLOWED_PAYMENT_PROOF_TYPES = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
    ".pdf": {"application/pdf"},
}


@dataclass(frozen=True)
class PaymentReviewItem:
    """Information displayed on the admin payment review page."""

    proof: PaymentProof
    booking: Booking
    ticket: Ticket
    concert: Concert


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


def get_payment_review_items(
    session: Session,
) -> list[PaymentReviewItem]:
    """Return all payment proofs waiting for admin review."""

    proofs = session.exec(select(PaymentProof).order_by(col(PaymentProof.id).desc())).all()

    review_items: list[PaymentReviewItem] = []

    for proof in proofs:
        booking = session.get(
            Booking,
            proof.booking_id,
        )

        if booking is None:
            continue

        ticket = session.get(
            Ticket,
            booking.ticket_id,
        )

        if ticket is None:
            continue

        concert = session.get(
            Concert,
            ticket.concert_id,
        )

        if concert is None:
            continue

        review_items.append(
            PaymentReviewItem(
                proof=proof,
                booking=booking,
                ticket=ticket,
                concert=concert,
            )
        )

    return review_items


def get_payment_review_item(
    proof_id: int,
    session: Session,
) -> PaymentReviewItem:
    """Retrieve one payment proof and its related booking details."""

    proof = session.get(
        PaymentProof,
        proof_id,
    )

    if proof is None:
        raise HTTPException(
            status_code=404,
            detail="Payment proof not found.",
        )

    booking = session.get(
        Booking,
        proof.booking_id,
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found.",
        )

    ticket = session.get(
        Ticket,
        booking.ticket_id,
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found.",
        )

    concert = session.get(
        Concert,
        ticket.concert_id,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found.",
        )

    return PaymentReviewItem(
        proof=proof,
        booking=booking,
        ticket=ticket,
        concert=concert,
    )


def get_payment_proof_path(
    proof: PaymentProof,
) -> Path:
    """Resolve a stored proof path without allowing path traversal."""

    stored_path = (UPLOAD_DIR / Path(proof.filename).name).resolve()

    upload_root = UPLOAD_DIR.resolve()

    if stored_path.parent != upload_root:
        raise HTTPException(
            status_code=404,
            detail="Payment proof file not found.",
        )

    if not stored_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Payment proof file not found.",
        )

    return stored_path


def approve_payment_proof(
    proof_id: int,
    session: Session,
) -> PaymentReviewItem:
    """Approve payment proof and confirm its booking."""

    item = get_payment_review_item(
        proof_id,
        session,
    )

    if item.booking.status == "confirmed":
        raise HTTPException(
            status_code=409,
            detail="This booking has already been confirmed.",
        )

    if item.booking.status != "payment_uploaded":
        raise HTTPException(
            status_code=409,
            detail=("Only uploaded payment proofs " "can be approved."),
        )

    item.booking.status = "confirmed"

    session.add(
        item.booking,
    )

    generate_eticket(
        item.booking,
        session,
    )

    session.commit()
    session.refresh(
        item.booking,
    )

    return item


def reject_payment_proof(
    proof_id: int,
    session: Session,
) -> Booking:
    """Reject proof and allow the attendee to upload another file."""

    item = get_payment_review_item(
        proof_id,
        session,
    )

    if item.booking.status != "payment_uploaded":
        raise HTTPException(
            status_code=409,
            detail=("Only uploaded payment proofs " "can be rejected."),
        )

    stored_path = UPLOAD_DIR / Path(item.proof.filename).name

    item.booking.status = "pending_payment"

    session.delete(item.proof)
    session.add(item.booking)
    session.commit()
    session.refresh(item.booking)

    stored_path.unlink(missing_ok=True)

    return item.booking
