from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.models import AttendeeCreate, OrganiserCreate, OrganiserRead, User, UserRead
from concert_portal.services.users import (
    find_organiser_by_registration_number,
    find_user_by_email,
    register_attendee_record,
    register_organiser_record,
)
from concert_portal.validation import (
    validate_attendee_registration,
    validate_organiser_registration,
)
from concert_portal.web import templates

router = APIRouter()


@router.post(
    "/users/attendees",
    response_model=UserRead,
    status_code=201,
)
def register_attendee(
    data: AttendeeCreate,
    session: Session = Depends(get_session),
) -> User:
    """US01 — Register a new attendee account."""

    return register_attendee_record(
        data.name,
        data.email,
        data.phone,
        data.password,
        session,
    )


@router.get("/register/attendee", response_class=HTMLResponse)
def attendee_registration_form(
    request: Request,
    registered: bool = False,
) -> HTMLResponse:
    """Show the attendee-registration form."""

    return templates.TemplateResponse(
        request,
        "attendee_register.html",
        {
            "errors": {},
            "values": {},
            "registered": registered,
        },
    )


@router.post("/register/attendee", response_model=None)
def attendee_registration_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Validate and process attendee registration."""

    errors, values = validate_attendee_registration(
        name,
        email,
        phone,
        password,
    )

    if not errors and find_user_by_email(values["email"], session) is not None:
        errors["email"] = "An account with this email already exists."

    if errors:
        return templates.TemplateResponse(
            request,
            "attendee_register.html",
            {
                "errors": errors,
                "values": values,
                "registered": False,
            },
            status_code=422,
        )

    register_attendee_record(
        values["name"],
        values["email"],
        values["phone"],
        password,
        session,
    )

    return RedirectResponse(
        url="/register/attendee?registered=true",
        status_code=303,
    )


@router.post(
    "/users/organisers",
    response_model=OrganiserRead,
    status_code=201,
)
def register_organiser(
    data: OrganiserCreate,
    session: Session = Depends(get_session),
) -> OrganiserRead:
    """US02 — Submit a new organiser-registration request."""

    return register_organiser_record(
        data.name,
        data.email,
        data.phone,
        data.password,
        data.organisation_name,
        data.registration_number,
        data.organisation_address,
        session,
    )


@router.get("/register/organiser", response_class=HTMLResponse)
def organiser_registration_form(
    request: Request,
    registered: bool = False,
) -> HTMLResponse:
    """Show the organiser-registration form."""

    return templates.TemplateResponse(
        request,
        "organiser_register.html",
        {
            "errors": {},
            "values": {},
            "registered": registered,
        },
    )


@router.post("/register/organiser", response_model=None)
def organiser_registration_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    organisation_name: str = Form(""),
    registration_number: str = Form(""),
    organisation_address: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Validate and process an organiser-registration request."""

    errors, values = validate_organiser_registration(
        name,
        email,
        phone,
        password,
        organisation_name,
        registration_number,
        organisation_address,
    )

    if not errors:
        if find_user_by_email(values["email"], session) is not None:
            errors["email"] = "An account with this email already exists."

        if (
            find_organiser_by_registration_number(
                values["registration_number"],
                session,
            )
            is not None
        ):
            errors["registration_number"] = (
                "An organiser request with this registration number already exists."
            )

    if errors:
        return templates.TemplateResponse(
            request,
            "organiser_register.html",
            {
                "errors": errors,
                "values": values,
                "registered": False,
            },
            status_code=422,
        )

    register_organiser_record(
        values["name"],
        values["email"],
        values["phone"],
        password,
        values["organisation_name"],
        values["registration_number"],
        values["organisation_address"],
        session,
    )

    return RedirectResponse(
        url="/register/organiser?registered=true",
        status_code=303,
    )
