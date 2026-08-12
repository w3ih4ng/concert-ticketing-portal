import os

from fastapi import HTTPException, Request
from pwdlib import PasswordHash
from sqlmodel import Session, select

from concert_portal.models import OrganiserProfile, User
from concert_portal.validation import normalize_email

password_hash = PasswordHash.recommended()

LOGIN_ERROR_MESSAGE = "Invalid email or password."
PENDING_ORGANISER_MESSAGE = "Your organiser account is still pending approval."
REJECTED_ORGANISER_MESSAGE = "Your organiser registration was rejected."
SESSION_SECRET_KEY = os.getenv(
    "SESSION_SECRET_KEY",
    "concert-portal-development-secret",
)


def authenticate_user(email: str, password: str, session: Session) -> User | None:
    """Authenticate a registered user without revealing which field failed."""

    normalized_email = normalize_email(email)
    user = session.exec(select(User).where(User.email == normalized_email)).first()

    if user is None:
        return None

    if not password_hash.verify(password, user.password_hash):
        return None

    return user


def create_login_session(request: Request, user: User) -> None:
    """Store only the minimum user identity required by the session."""

    if user.id is None:
        raise HTTPException(
            status_code=500,
            detail="User session could not be created.",
        )

    request.session.clear()
    request.session["user_id"] = user.id


def get_session_user(request: Request, session: Session) -> User | None:
    """Return the currently logged-in user, if the session is valid."""

    user_id = request.session.get("user_id")

    if not isinstance(user_id, int):
        return None

    user = session.get(User, user_id)

    if user is None:
        request.session.clear()
        return None

    return user


def organiser_account_is_approved(user: User, session: Session) -> bool:
    """Return whether an organiser profile has been approved."""

    if user.id is None:
        return False

    profile = session.exec(
        select(OrganiserProfile).where(OrganiserProfile.user_id == user.id)
    ).first()

    return profile is not None and profile.status == "approved"


def get_organiser_account_status(
    user: User,
    session: Session,
) -> str | None:
    """Return the organiser account approval status."""

    if user.id is None:
        return None

    profile = session.exec(
        select(OrganiserProfile).where(
            OrganiserProfile.user_id == user.id,
        )
    ).first()

    if profile is None:
        return None

    return profile.status


def role_redirect_url(role: str) -> str:
    """Return the destination associated with a user role."""

    destinations = {
        "attendee": "/",
        "organiser": "/organiser/dashboard",
        "staff": "/staff/dashboard",
        "admin": "/admin/dashboard",
    }

    return destinations.get(role, "/")
