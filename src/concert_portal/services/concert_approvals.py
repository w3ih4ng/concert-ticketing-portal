from fastapi import HTTPException
from sqlmodel import Session, func, select

from concert_portal.models import Concert, ConcertApproval


def get_concert_approval(
    concert_id: int,
    session: Session,
) -> ConcertApproval | None:
    """Return the approval record for one concert."""

    return session.exec(
        select(ConcertApproval).where(
            ConcertApproval.concert_id == concert_id,
        )
    ).first()


def get_concert_approval_status(
    concert_id: int,
    session: Session,
) -> str:
    """Return a readable approval status for a concert."""

    approval = get_concert_approval(
        concert_id,
        session,
    )

    if approval is None:
        return "draft"

    return approval.status


def submit_concert_for_approval(
    concert_id: int,
    session: Session,
) -> ConcertApproval:
    """Submit a concert for administrator approval."""

    concert = session.get(
        Concert,
        concert_id,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    existing = get_concert_approval(
        concert_id,
        session,
    )

    if existing is None:
        approval = ConcertApproval(
            concert_id=concert_id,
            status="pending",
        )

        session.add(
            approval,
        )
        session.commit()
        session.refresh(
            approval,
        )

        return approval

    if existing.status == "pending":
        raise HTTPException(
            status_code=409,
            detail=("This concert is already pending approval."),
        )

    if existing.status == "approved":
        raise HTTPException(
            status_code=409,
            detail="This concert has already been approved.",
        )

    existing.status = "pending"

    session.add(
        existing,
    )
    session.commit()
    session.refresh(
        existing,
    )

    return existing


def is_concert_locked(
    concert_id: int,
    session: Session,
) -> bool:
    """Return whether organiser editing should be locked."""

    status = get_concert_approval_status(
        concert_id,
        session,
    )

    return status in {
        "pending",
        "approved",
    }


def ensure_concert_is_editable(
    concert_id: int,
    session: Session,
) -> None:
    """Raise an error when a submitted concert is locked."""

    if is_concert_locked(
        concert_id,
        session,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This concert cannot be edited "
                "while it is awaiting approval "
                "or after approval."
            ),
        )


def get_pending_concert_count(
    session: Session,
) -> int:
    """Return the number of concerts awaiting admin review."""

    count = session.exec(
        select(func.count())
        .select_from(
            ConcertApproval,
        )
        .where(
            ConcertApproval.status == "pending",
        )
    ).one()

    return int(count)
