from fastapi import HTTPException
from sqlmodel import Session, select

from concert_portal.models import OrganiserProfile, OrganiserRead, User
from concert_portal.security import password_hash
from concert_portal.validation import (
    normalize_email,
    validate_attendee_registration,
    validate_organiser_registration,
)


def find_user_by_email(email: str, session: Session) -> User | None:
    """Find an existing user using a normalized email address."""

    normalized_email = normalize_email(email)

    return session.exec(select(User).where(User.email == normalized_email)).first()


def register_attendee_record(
    name: str,
    email: str,
    phone: str,
    password: str,
    session: Session,
) -> User:
    """Validate and save a new attendee account."""

    errors, values = validate_attendee_registration(
        name,
        email,
        phone,
        password,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    if find_user_by_email(values["email"], session) is not None:
        raise HTTPException(
            status_code=409,
            detail={"email": "An account with this email already exists."},
        )

    user = User(
        name=values["name"],
        email=values["email"],
        phone=values["phone"],
        role="attendee",
        password_hash=password_hash.hash(password),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def find_organiser_by_registration_number(
    registration_number: str,
    session: Session,
) -> OrganiserProfile | None:
    """Find an organiser request by registration number."""

    normalized_number = registration_number.strip().upper()

    return session.exec(
        select(OrganiserProfile).where(OrganiserProfile.registration_number == normalized_number)
    ).first()


def organiser_response(user: User, profile: OrganiserProfile) -> OrganiserRead:
    """Build the safe organiser-registration response."""

    if user.id is None or profile.id is None:
        raise HTTPException(
            status_code=500,
            detail="Organiser registration could not be completed.",
        )

    return OrganiserRead(
        id=profile.id,
        user_id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        organisation_name=profile.organisation_name,
        registration_number=profile.registration_number,
        organisation_address=profile.organisation_address,
        status=profile.status,
    )


def register_organiser_record(
    name: str,
    email: str,
    phone: str,
    password: str,
    organisation_name: str,
    registration_number: str,
    organisation_address: str,
    session: Session,
) -> OrganiserRead:
    """Validate and save an organiser-registration request."""

    errors, values = validate_organiser_registration(
        name,
        email,
        phone,
        password,
        organisation_name,
        registration_number,
        organisation_address,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    duplicate_errors: dict[str, str] = {}

    if find_user_by_email(values["email"], session) is not None:
        duplicate_errors["email"] = "An account with this email already exists."

    if (
        find_organiser_by_registration_number(
            values["registration_number"],
            session,
        )
        is not None
    ):
        duplicate_errors["registration_number"] = (
            "An organiser request with this registration number already exists."
        )

    if duplicate_errors:
        raise HTTPException(
            status_code=409,
            detail=duplicate_errors,
        )

    user = User(
        name=values["name"],
        email=values["email"],
        phone=values["phone"],
        role="organiser",
        password_hash=password_hash.hash(password),
    )

    session.add(user)
    session.flush()

    if user.id is None:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Organiser account could not be created.",
        )

    profile = OrganiserProfile(
        user_id=user.id,
        organisation_name=values["organisation_name"],
        registration_number=values["registration_number"],
        organisation_address=values["organisation_address"],
        status="pending",
    )

    session.add(profile)
    session.commit()
    session.refresh(user)
    session.refresh(profile)

    return organiser_response(user, profile)
