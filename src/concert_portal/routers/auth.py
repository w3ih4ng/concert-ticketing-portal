from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.models import LoginRequest, LoginResponse
from concert_portal.security import (
    LOGIN_ERROR_MESSAGE,
    PENDING_ORGANISER_MESSAGE,
    authenticate_user,
    create_login_session,
    get_session_user,
    organiser_account_is_approved,
    role_redirect_url,
)
from concert_portal.validation import normalize_email
from concert_portal.web import templates

router = APIRouter()


@router.post(
    "/users/login",
    response_model=LoginResponse,
)
def login_api(
    data: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """US04 — Authenticate a user and create a signed session."""

    user = authenticate_user(
        data.email,
        data.password,
        session,
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail=LOGIN_ERROR_MESSAGE,
        )

    if user.role == "organiser" and not organiser_account_is_approved(
        user,
        session,
    ):
        raise HTTPException(
            status_code=403,
            detail=PENDING_ORGANISER_MESSAGE,
        )

    create_login_session(request, user)

    if user.id is None:
        raise HTTPException(
            status_code=500,
            detail="User session could not be created.",
        )

    return LoginResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        redirect_url=role_redirect_url(user.role),
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    logged_out: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    """Show the login form unless the user is already logged in."""

    current_user = get_session_user(request, session)

    if current_user is not None:
        return RedirectResponse(
            url=role_redirect_url(current_user.role),
            status_code=303,
        )

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": None,
            "email": "",
            "logged_out": logged_out == "true",
        },
    )


@router.post("/login", response_model=None)
def login_submit(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
) -> Response:
    """Validate credentials and redirect the user based on role."""

    normalized_email = normalize_email(email)

    if not normalized_email or not password:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": LOGIN_ERROR_MESSAGE,
                "email": normalized_email,
                "logged_out": False,
            },
            status_code=422,
        )

    user = authenticate_user(
        normalized_email,
        password,
        session,
    )

    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": LOGIN_ERROR_MESSAGE,
                "email": normalized_email,
                "logged_out": False,
            },
            status_code=401,
        )

    if user.role == "organiser" and not organiser_account_is_approved(
        user,
        session,
    ):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": PENDING_ORGANISER_MESSAGE,
                "email": normalized_email,
                "logged_out": False,
            },
            status_code=403,
        )

    create_login_session(request, user)

    return RedirectResponse(
        url=role_redirect_url(user.role),
        status_code=303,
    )


@router.post("/logout", response_model=None)
def logout(request: Request) -> RedirectResponse:
    """US05 — Clear the current user session and return to login."""

    request.session.clear()

    return RedirectResponse(
        url="/login?logged_out=true",
        status_code=303,
    )
