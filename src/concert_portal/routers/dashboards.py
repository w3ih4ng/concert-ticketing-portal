from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.security import get_session_user, role_redirect_url
from concert_portal.services.concert_approvals import (
    get_pending_concert_count,
)
from concert_portal.web import templates

router = APIRouter()


def render_role_dashboard(
    request: Request,
    required_role: str,
    session: Session,
) -> Response:
    """Render a dashboard only when the logged-in role matches."""

    user = get_session_user(
        request,
        session,
    )

    if user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    if user.role != required_role:
        return RedirectResponse(
            url=role_redirect_url(
                user.role,
            ),
            status_code=303,
        )

    pending_concert_count = 0

    if required_role == "admin":
        pending_concert_count = get_pending_concert_count(
            session,
        )

    return templates.TemplateResponse(
        request,
        "role_dashboard.html",
        {
            "user": user,
            "dashboard_role": required_role,
            "pending_concert_count": pending_concert_count,
        },
    )


@router.get(
    "/organiser/dashboard",
    response_class=HTMLResponse,
)
def organiser_dashboard(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Show the organiser dashboard."""

    return render_role_dashboard(
        request,
        "organiser",
        session,
    )


@router.get(
    "/staff/dashboard",
    response_class=HTMLResponse,
)
def staff_dashboard(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Show the staff dashboard."""

    return render_role_dashboard(
        request,
        "staff",
        session,
    )


@router.get(
    "/admin/dashboard",
    response_class=HTMLResponse,
)
def admin_dashboard(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Show the administrator dashboard."""

    return render_role_dashboard(
        request,
        "admin",
        session,
    )
