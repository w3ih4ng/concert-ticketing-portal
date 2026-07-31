from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.services.payments import (
    MAX_PAYMENT_PROOF_SIZE,
    generate_payment_proof_filename,
    get_booking_for_payment_upload,
    save_payment_proof_record,
    validate_payment_proof,
)
from concert_portal.web import UPLOAD_DIR

router = APIRouter()


def _payment_error_redirect(
    booking_id: int,
    message: str,
) -> RedirectResponse:
    """Return to the booking page with an upload error."""

    encoded_message = quote(
        message,
        safe="",
    )

    return RedirectResponse(
        url=(f"/bookings/{booking_id}" f"?payment_error={encoded_message}"),
        status_code=303,
    )


@router.post("/bookings/{booking_id}/payment-proof")
def upload_payment_proof(
    booking_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """ENH03 — Validate and securely store payment proof."""

    try:
        booking = get_booking_for_payment_upload(
            booking_id,
            session,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return _payment_error_redirect(
            booking_id,
            str(exc.detail),
        )

    try:
        content = file.file.read(MAX_PAYMENT_PROOF_SIZE + 1)

        extension = validate_payment_proof(
            filename=file.filename,
            content_type=file.content_type,
            content=content,
        )
    except HTTPException as exc:
        return _payment_error_redirect(
            booking_id,
            str(exc.detail),
        )
    finally:
        file.file.close()

    stored_filename = generate_payment_proof_filename(
        booking_id,
        extension,
    )

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stored_path = UPLOAD_DIR / stored_filename

    try:
        stored_path.write_bytes(content)

        save_payment_proof_record(
            booking,
            stored_filename,
            session,
        )
    except HTTPException as exc:
        stored_path.unlink(missing_ok=True)

        if exc.status_code == 404:
            raise

        return _payment_error_redirect(
            booking_id,
            str(exc.detail),
        )
    except OSError:
        stored_path.unlink(missing_ok=True)

        return _payment_error_redirect(
            booking_id,
            ("The payment proof could not be saved. " "Please try again."),
        )

    return RedirectResponse(
        url=f"/bookings/{booking_id}",
        status_code=303,
    )
