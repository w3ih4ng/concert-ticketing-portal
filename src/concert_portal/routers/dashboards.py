from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    Response,
)
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
from concert_portal.services.etickets import (
    check_in_eticket,
    verify_eticket_code,
)
from concert_portal.services.users import create_staff_record
from concert_portal.web import templates

router = APIRouter()

STAFF_CREATED_MESSAGE = "Staff account created successfully."
CHECK_IN_SUCCESS_MESSAGE = "Attendee checked in successfully."
CHECK_IN_DUPLICATE_MESSAGE = "This e-ticket has already been checked in."
CHECK_IN_INVALID_MESSAGE = "Valid e-ticket not found."


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
            "check_in_message": None,
            "check_in_error": None,
        },
    )


@router.post(
    "/staff/tickets/check-in",
    response_class=HTMLResponse,
)
def staff_ticket_check_in(
    request: Request,
    code: str = Form(""),
    session: Session = Depends(get_session),
) -> Response:
    """SCRUM-149 — Mark a verified attendee e-ticket as checked in."""

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

    normalized_code = code.strip().upper()

    if not normalized_code:
        return templates.TemplateResponse(
            request,
            "staff_ticket_verify.html",
            {
                "user": user,
                "code": code,
                "searched": True,
                "result": None,
                "check_in_message": None,
                "check_in_error": CHECK_IN_INVALID_MESSAGE,
            },
            status_code=404,
        )

    try:
        result = check_in_eticket(
            normalized_code,
            session,
        )

    except HTTPException as exc:
        verification_result = verify_eticket_code(
            normalized_code,
            session,
        )

        if exc.status_code == 409:
            error = CHECK_IN_DUPLICATE_MESSAGE
        else:
            error = CHECK_IN_INVALID_MESSAGE

        return templates.TemplateResponse(
            request,
            "staff_ticket_verify.html",
            {
                "user": user,
                "code": normalized_code,
                "searched": True,
                "result": verification_result,
                "check_in_message": None,
                "check_in_error": error,
            },
            status_code=exc.status_code,
        )

    return templates.TemplateResponse(
        request,
        "staff_ticket_verify.html",
        {
            "user": user,
            "code": normalized_code,
            "searched": True,
            "result": result,
            "check_in_message": CHECK_IN_SUCCESS_MESSAGE,
            "check_in_error": None,
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


@router.get(
    "/admin/staff/new",
    response_class=HTMLResponse,
)
def admin_staff_create_page(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """SCRUM-225 — Show the admin staff-account creation form."""

    user = get_session_user(
        request,
        session,
    )

    if user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    if user.role != "admin":
        return RedirectResponse(
            url=role_redirect_url(
                user.role,
            ),
            status_code=303,
        )

    return templates.TemplateResponse(
        request,
        "admin_staff_create.html",
        {
            "user": user,
            "errors": {},
            "values": {
                "name": "",
                "email": "",
                "phone": "",
            },
            "created": False,
        },
    )


@router.post(
    "/admin/staff/new",
    response_class=HTMLResponse,
)
def admin_staff_create_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
) -> Response:
    """SCRUM-225 — Create a staff account as an administrator."""

    user = get_session_user(
        request,
        session,
    )

    if user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    if user.role != "admin":
        return RedirectResponse(
            url=role_redirect_url(
                user.role,
            ),
            status_code=303,
        )

    values = {
        "name": name,
        "email": email,
        "phone": phone,
    }

    try:
        create_staff_record(
            name,
            email,
            phone,
            password,
            session,
        )

    except HTTPException as exc:
        errors: dict[str, str]

        if isinstance(
            exc.detail,
            dict,
        ):
            errors = {str(key): str(value) for key, value in exc.detail.items()}
        else:
            errors = {
                "general": str(
                    exc.detail,
                )
            }

        return templates.TemplateResponse(
            request,
            "admin_staff_create.html",
            {
                "user": user,
                "errors": errors,
                "values": values,
                "created": False,
            },
            status_code=exc.status_code,
        )

    return templates.TemplateResponse(
        request,
        "admin_staff_create.html",
        {
            "user": user,
            "errors": {},
            "values": {
                "name": "",
                "email": "",
                "phone": "",
            },
            "created": True,
            "message": STAFF_CREATED_MESSAGE,
        },
        status_code=201,
    )
