from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import (
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
from concert_portal.services.users import (
    approve_organiser,
    get_pending_organisers,
    reject_organiser,
)
from concert_portal.web import templates

router = APIRouter()


def _require_admin(
    request: Request,
    session: Session,
) -> Response | None:
    """Allow only administrators to access organiser review functions."""

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


def _organiser_review_redirect(
    *,
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Return to organiser review with a feedback message."""

    if message is not None:
        encoded = quote(
            message,
            safe="",
        )

        return RedirectResponse(
            url=f"/admin/organisers?message={encoded}",
            status_code=303,
        )

    encoded = quote(
        error or "Something went wrong.",
        safe="",
    )

    return RedirectResponse(
        url=f"/admin/organisers?error={encoded}",
        status_code=303,
    )


@router.get(
    "/admin/organisers",
    response_class=HTMLResponse,
)
def admin_organiser_review_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    """US03 — Show pending organiser registrations to administrators."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    organisers = get_pending_organisers(
        session,
    )

    return templates.TemplateResponse(
        request,
        "admin_organiser_review.html",
        {
            "organisers": organisers,
            "message": message,
            "error": error,
        },
    )


@router.post(
    "/admin/organisers/{profile_id}/approve",
)
def admin_approve_organiser(
    profile_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Approve an organiser registration request."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    try:
        profile = approve_organiser(
            profile_id,
            session,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return _organiser_review_redirect(
            error=str(exc.detail),
        )

    return _organiser_review_redirect(
        message=(f"Organiser registration #{profile.id} " "was approved successfully."),
    )


@router.post(
    "/admin/organisers/{profile_id}/reject",
)
def admin_reject_organiser(
    profile_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Reject an organiser registration request."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    try:
        profile = reject_organiser(
            profile_id,
            session,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return _organiser_review_redirect(
            error=str(exc.detail),
        )

    return _organiser_review_redirect(
        message=(f"Organiser registration #{profile.id} " "was rejected."),
    )
