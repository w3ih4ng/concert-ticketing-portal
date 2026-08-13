from fastapi import HTTPException
from sqlmodel import Session, select

from concert_portal.models import OrganiserProfile, OrganiserRead, User
from concert_portal.security import password_hash
from concert_portal.validation import (
    normalize_email,
    validate_attendee_registration,
    validate_organiser_registration,
    validate_profile_update,
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


def create_staff_record(
    name: str,
    email: str,
    phone: str,
    password: str,
    session: Session,
) -> User:
    """Validate and create a staff account."""

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

    if (
        find_user_by_email(
            values["email"],
            session,
        )
        is not None
    ):
        raise HTTPException(
            status_code=409,
            detail={"email": ("An account with this email already exists.")},
        )

    user = User(
        name=values["name"],
        email=values["email"],
        phone=values["phone"],
        role="staff",
        password_hash=password_hash.hash(
            password,
        ),
    )

    session.add(
        user,
    )
    session.commit()
    session.refresh(
        user,
    )

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


def get_pending_organisers(
    session: Session,
) -> list[OrganiserRead]:
    """Return organiser registration requests waiting for admin review."""

    profiles = session.exec(
        select(OrganiserProfile).where(
            OrganiserProfile.status == "pending",
        )
    ).all()

    organisers: list[OrganiserRead] = []

    for profile in profiles:
        user = session.get(
            User,
            profile.user_id,
        )

        if user is None:
            continue

        organisers.append(
            organiser_response(
                user,
                profile,
            )
        )

    return organisers


def get_organiser_profile(
    profile_id: int,
    session: Session,
) -> OrganiserProfile:
    """Return an organiser profile or raise 404."""

    profile = session.get(
        OrganiserProfile,
        profile_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Organiser registration request not found.",
        )

    return profile


def approve_organiser(
    profile_id: int,
    session: Session,
) -> OrganiserProfile:
    """Approve a pending organiser registration request."""

    profile = get_organiser_profile(
        profile_id,
        session,
    )

    if profile.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending organiser requests can be approved.",
        )

    profile.status = "approved"

    session.add(profile)
    session.commit()
    session.refresh(profile)

    return profile


def reject_organiser(
    profile_id: int,
    session: Session,
) -> OrganiserProfile:
    """Reject a pending organiser registration request."""

    profile = get_organiser_profile(
        profile_id,
        session,
    )

    if profile.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending organiser requests can be rejected.",
        )

    profile.status = "rejected"

    session.add(profile)
    session.commit()
    session.refresh(profile)

    return profile


def update_user_profile(
    user: User,
    name: str,
    email: str,
    phone: str,
    password: str,
    session: Session,
) -> User:
    """Validate and update a user's profile."""

    errors, values = validate_profile_update(
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

    existing_user = find_user_by_email(
        values["email"],
        session,
    )

    if existing_user is not None and existing_user.id != user.id:
        raise HTTPException(
            status_code=409,
            detail={
                "email": "An account with this email already exists.",
            },
        )

    user.name = values["name"]
    user.email = values["email"]
    user.phone = values["phone"]

    if password:
        user.password_hash = password_hash.hash(password)

    session.add(user)
    session.commit()
    session.refresh(user)

    return user
