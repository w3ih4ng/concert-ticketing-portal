from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.security import get_session_user
from concert_portal.services.users import update_user_profile
from concert_portal.validation import validate_profile_update
from concert_portal.web import templates

router = APIRouter()


@router.get(
    "/profile",
    response_class=HTMLResponse,
)
def profile_page(
    request: Request,
    updated: bool = False,
    session: Session = Depends(get_session),
) -> Response:
    """US06 — Display the currently logged-in user's profile."""

    user = get_session_user(
        request,
        session,
    )

    if user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "user": user,
            "errors": {},
            "values": {
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
            },
            "updated": updated,
        },
    )


@router.post(
    "/profile",
    response_model=None,
)
def profile_update(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
) -> Response:
    """Validate and save profile changes."""

    user = get_session_user(
        request,
        session,
    )

    if user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    errors, values = validate_profile_update(
        name,
        email,
        phone,
        password,
    )

    if errors:
        return templates.TemplateResponse(
            request,
            "profile.html",
            {
                "user": user,
                "errors": errors,
                "values": values,
                "updated": False,
            },
            status_code=422,
        )

    try:
        update_user_profile(
            user,
            values["name"],
            values["email"],
            values["phone"],
            password,
            session,
        )
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            errors = exc.detail
        else:
            errors = {
                "general": str(exc.detail),
            }

        return templates.TemplateResponse(
            request,
            "profile.html",
            {
                "user": user,
                "errors": errors,
                "values": values,
                "updated": False,
            },
            status_code=exc.status_code,
        )

    return RedirectResponse(
        url="/profile?updated=true",
        status_code=303,
    )
