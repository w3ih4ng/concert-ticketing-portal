from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.security import (
    get_session_user,
    role_redirect_url,
)
from concert_portal.services.dashboard_summary import (
    AdminDashboardSummary,
    get_admin_dashboard_summary,
)
from concert_portal.services.etickets import verify_eticket_code
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

    admin_summary: AdminDashboardSummary | None = None

    if required_role == "admin":
        admin_summary = get_admin_dashboard_summary(
            session,
        )

    return templates.TemplateResponse(
        request,
        "role_dashboard.html",
        {
            "user": user,
            "dashboard_role": required_role,
            "admin_summary": admin_summary,
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
    "/staff/tickets/verify",
    response_class=HTMLResponse,
)
def staff_ticket_verification_page(
    request: Request,
    code: str = "",
    session: Session = Depends(get_session),
) -> Response:
    """SCRUM-146 — Allow staff to verify an attendee e-ticket."""

    user = get_session_user(
        request,
        session,
    )

    if user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    if user.role != "staff":
        return RedirectResponse(
            url=role_redirect_url(
                user.role,
            ),
            status_code=303,
        )

    searched = bool(code.strip())

    result = None

    if searched:
        result = verify_eticket_code(
            code,
            session,
        )

    return templates.TemplateResponse(
        request,
        "staff_ticket_verify.html",
        {
            "user": user,
            "code": code,
            "searched": searched,
            "result": result,
        },
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
