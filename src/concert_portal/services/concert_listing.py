from dataclasses import dataclass

from sqlmodel import Session, select

from concert_portal.models import (
    Concert,
    ConcertApproval,
    ConcertPoster,
)


@dataclass(frozen=True)
class PublicConcertItem:
    """Concert information displayed on the public listing page."""

    concert: Concert
    poster: ConcertPoster | None


def get_approved_concerts(
    session: Session,
    *,
    search: str = "",
    event_date: str = "",
) -> list[PublicConcertItem]:
    """Return approved concerts matching optional attendee filters."""

    approvals = session.exec(
        select(ConcertApproval).where(
            ConcertApproval.status == "approved",
        )
    ).all()

    normalized_search = search.strip().lower()
    normalized_date = event_date.strip()

    items: list[PublicConcertItem] = []

    for approval in approvals:
        concert = session.get(
            Concert,
            approval.concert_id,
        )

        if concert is None:
            continue

        if normalized_search:
            searchable_text = (
                f"{concert.title} " f"{concert.venue} " f"{concert.organiser}"
            ).lower()

            if normalized_search not in searchable_text:
                continue

        if normalized_date and concert.date != normalized_date:
            continue

        poster = session.exec(
            select(ConcertPoster).where(
                ConcertPoster.concert_id == concert.id,
            )
        ).first()

        items.append(
            PublicConcertItem(
                concert=concert,
                poster=poster,
            )
        )

    items.sort(
        key=lambda item: (
            item.concert.date,
            item.concert.title.lower(),
        )
    )

    return items
