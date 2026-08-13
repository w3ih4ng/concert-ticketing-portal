from dataclasses import dataclass

from sqlmodel import Session, func, select

from concert_portal.models import (
    Booking,
    Concert,
    ConcertApproval,
    OrganiserProfile,
    User,
)


@dataclass(frozen=True)
class AdminDashboardSummary:
    """Summary statistics displayed on the admin dashboard."""

    total_users: int
    total_concerts: int
    total_bookings: int
    pending_organisers: int
    pending_concerts: int
    pending_payments: int


def _count_all(
    model: type[User] | type[Concert] | type[Booking],
    session: Session,
) -> int:
    """Return the number of rows in a table."""

    count = session.exec(select(func.count()).select_from(model)).one()

    return int(count)


def get_admin_dashboard_summary(
    session: Session,
) -> AdminDashboardSummary:
    """Return statistics required by the administrator dashboard."""

    pending_organisers = session.exec(
        select(func.count())
        .select_from(OrganiserProfile)
        .where(
            OrganiserProfile.status == "pending",
        )
    ).one()

    pending_concerts = session.exec(
        select(func.count())
        .select_from(ConcertApproval)
        .where(
            ConcertApproval.status == "pending",
        )
    ).one()

    pending_payments = session.exec(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.status == "payment_uploaded",
        )
    ).one()

    return AdminDashboardSummary(
        total_users=_count_all(
            User,
            session,
        ),
        total_concerts=_count_all(
            Concert,
            session,
        ),
        total_bookings=_count_all(
            Booking,
            session,
        ),
        pending_organisers=int(
            pending_organisers,
        ),
        pending_concerts=int(
            pending_concerts,
        ),
        pending_payments=int(
            pending_payments,
        ),
    )
