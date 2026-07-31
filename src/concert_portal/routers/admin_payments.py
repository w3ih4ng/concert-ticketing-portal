from pathlib import Path
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
)
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.security import (
    get_session_user,
    role_redirect_url,
)
from concert_portal.services.payments import (
    approve_payment_proof,
    get_payment_proof_path,
    get_payment_review_item,
    get_payment_review_items,
    reject_payment_proof,
)
from concert_portal.web import templates

router = APIRouter()


def _require_admin(
    request: Request,
    session: Session,
) -> Response | None:
    """Redirect unauthenticated and non-admin users."""

    current_user = get_session_user(
        request,
        session,
    )

    if current_user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    if current_user.role != "admin":
        return RedirectResponse(
            url=role_redirect_url(current_user.role),
            status_code=303,
        )

    return None


def _admin_payment_redirect(
    *,
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Return to the payment review list with feedback."""

    if message is not None:
        encoded = quote(
            message,
            safe="",
        )

        return RedirectResponse(
            url=f"/admin/payments?message={encoded}",
            status_code=303,
        )

    encoded = quote(
        error or "Something went wrong.",
        safe="",
    )

    return RedirectResponse(
        url=f"/admin/payments?error={encoded}",
        status_code=303,
    )


@router.get(
    "/admin/payments",
    response_class=HTMLResponse,
)
def admin_payment_review_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    """US25 — Show payment proofs to administrators."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    review_items = get_payment_review_items(
        session,
    )

    return templates.TemplateResponse(
        request,
        "admin_payment_review.html",
        {
            "review_items": review_items,
            "message": message,
            "error": error,
        },
    )


@router.get(
    "/admin/payment-proofs/{proof_id}/file",
    response_model=None,
)
def admin_payment_proof_file(
    proof_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Securely display a payment-proof file to an admin."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    item = get_payment_review_item(
        proof_id,
        session,
    )

    stored_path = get_payment_proof_path(
        item.proof,
    )

    extension = Path(item.proof.filename).suffix.lower()

    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".pdf": "application/pdf",
    }

    media_type = media_types.get(
        extension,
        "application/octet-stream",
    )

    return FileResponse(
        path=stored_path,
        media_type=media_type,
        filename=item.proof.filename,
        content_disposition_type="inline",
    )


@router.post(
    "/admin/payment-proofs/{proof_id}/approve",
)
def admin_approve_payment_proof(
    proof_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Approve payment proof and confirm the booking."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    try:
        item = approve_payment_proof(
            proof_id,
            session,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return _admin_payment_redirect(
            error=str(exc.detail),
        )

    return _admin_payment_redirect(
        message=(f"Payment proof for booking " f"#{item.booking.id} was approved."),
    )


@router.post(
    "/admin/payment-proofs/{proof_id}/reject",
)
def admin_reject_payment_proof(
    proof_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Reject payment proof and reopen payment upload."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    try:
        booking = reject_payment_proof(
            proof_id,
            session,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return _admin_payment_redirect(
            error=str(exc.detail),
        )

    return _admin_payment_redirect(
        message=(
            f"Payment proof for booking "
            f"#{booking.id} was rejected. "
            "The attendee may upload a replacement."
        ),
    )
