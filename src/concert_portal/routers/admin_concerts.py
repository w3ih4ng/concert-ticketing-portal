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
from concert_portal.services.concert_approvals import (
    approve_concert,
    get_concert_review_item,
    get_pending_concert_review_items,
    reject_concert,
)
from concert_portal.web import templates

router = APIRouter()


def _require_admin(
    request: Request,
    session: Session,
) -> Response | None:
    """Allow only administrators to access concert approval."""

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
            url=role_redirect_url(
                current_user.role,
            ),
            status_code=303,
        )

    return None


def _concert_review_redirect(
    *,
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Return to the concert approval list with feedback."""

    if message is not None:
        encoded = quote(
            message,
            safe="",
        )

        return RedirectResponse(
            url=("/admin/concerts" f"?message={encoded}"),
            status_code=303,
        )

    encoded = quote(
        error or "Something went wrong.",
        safe="",
    )

    return RedirectResponse(
        url=("/admin/concerts" f"?error={encoded}"),
        status_code=303,
    )


@router.get(
    "/admin/concerts",
    response_class=HTMLResponse,
)
def admin_concert_review_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    """US — Show concerts awaiting administrator approval."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    review_items = get_pending_concert_review_items(
        session,
    )

    return templates.TemplateResponse(
        request,
        "admin_concert_review.html",
        {
            "review_items": review_items,
            "message": message,
            "error": error,
        },
    )


@router.get(
    "/admin/concerts/{concert_id}",
    response_class=HTMLResponse,
)
def admin_concert_review_detail(
    concert_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Show complete information for one submitted concert."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    item = get_concert_review_item(
        concert_id,
        session,
    )

    return templates.TemplateResponse(
        request,
        "admin_concert_review_detail.html",
        {
            "item": item,
        },
    )


@router.post(
    "/admin/concerts/{concert_id}/approve",
)
def admin_approve_concert(
    concert_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Approve a pending concert."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    try:
        approval = approve_concert(
            concert_id,
            session,
        )

    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return _concert_review_redirect(
            error=str(
                exc.detail,
            ),
        )

    return _concert_review_redirect(
        message=(f"Concert #{approval.concert_id} " "was approved successfully."),
    )


@router.post(
    "/admin/concerts/{concert_id}/reject",
)
def admin_reject_concert(
    concert_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Reject a pending concert."""

    redirect = _require_admin(
        request,
        session,
    )

    if redirect is not None:
        return redirect

    try:
        approval = reject_concert(
            concert_id,
            session,
        )

    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return _concert_review_redirect(
            error=str(
                exc.detail,
            ),
        )

    return _concert_review_redirect(
        message=(f"Concert #{approval.concert_id} " "was rejected."),
    )
