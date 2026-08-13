from fastapi.testclient import TestClient
from sqlmodel import Session, select

from concert_portal.models import (
    Concert,
    ConcertApproval,
    Ticket,
)


def _create_concert(
    session: Session,
) -> Concert:
    """Create a concert for approval-submission tests."""

    concert = Concert(
        title="Approval Test Concert",
        date="2030-08-01",
        venue="Test Stadium",
        organiser="Test Organiser",
    )

    session.add(
        concert,
    )
    session.commit()
    session.refresh(
        concert,
    )

    return concert


def test_draft_concert_shows_submit_button(
    client: TestClient,
    session: Session,
) -> None:
    """A draft concert can be submitted for approval."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.get(
        f"/concerts/{concert.id}",
    )

    assert response.status_code == 200
    assert "Draft" in response.text
    assert "Submit for approval" in response.text


def test_concert_can_be_submitted_for_approval(
    client: TestClient,
    session: Session,
) -> None:
    """Submitting creates a pending approval record."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/submit",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}?submitted=true")

    approval = session.exec(
        select(ConcertApproval).where(
            ConcertApproval.concert_id == concert.id,
        )
    ).first()

    assert approval is not None
    assert approval.status == "pending"


def test_pending_status_is_displayed(
    client: TestClient,
    session: Session,
) -> None:
    """Submitted concerts show pending approval status."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="pending",
    )

    session.add(
        approval,
    )
    session.commit()

    response = client.get(
        f"/concerts/{concert.id}",
    )

    assert response.status_code == 200
    assert "Pending approval" in response.text
    assert "Editing is temporarily locked" in response.text


def test_pending_concert_cannot_be_submitted_again(
    client: TestClient,
    session: Session,
) -> None:
    """A pending concert cannot be submitted twice."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="pending",
    )

    session.add(
        approval,
    )
    session.commit()

    response = client.post(
        f"/concerts/{concert.id}/submit",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/concerts/{concert.id}" "?approval_error=already_submitted"
    )


def test_pending_concert_edit_page_is_locked(
    client: TestClient,
    session: Session,
) -> None:
    """The edit page cannot be opened while approval is pending."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="pending",
    )

    session.add(
        approval,
    )
    session.commit()

    response = client.get(
        f"/concerts/{concert.id}/edit",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}" "?approval_error=locked")


def test_pending_concert_edit_post_is_locked(
    client: TestClient,
    session: Session,
) -> None:
    """Direct POST requests cannot bypass the edit lock."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="pending",
    )

    session.add(
        approval,
    )
    session.commit()

    response = client.post(
        f"/concerts/{concert.id}/edit",
        data={
            "title": "Changed Concert",
            "date": "2031-01-01",
            "venue": "Changed Venue",
            "organiser": "Changed Organiser",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    session.refresh(
        concert,
    )

    assert concert.title == "Approval Test Concert"
    assert concert.venue == "Test Stadium"


def test_pending_concert_cannot_add_ticket(
    client: TestClient,
    session: Session,
) -> None:
    """Ticket creation is locked once the concert is submitted."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="pending",
    )

    session.add(
        approval,
    )
    session.commit()

    response = client.post(
        "/tickets",
        json={
            "concert_id": concert.id,
            "category": "VIP",
            "price": 200,
            "quantity": 10,
        },
    )

    assert response.status_code == 409

    tickets = session.exec(
        select(Ticket).where(
            Ticket.concert_id == concert.id,
        )
    ).all()

    assert len(tickets) == 0


def test_rejected_concert_can_be_resubmitted(
    client: TestClient,
    session: Session,
) -> None:
    """Rejected concerts may be updated and submitted again."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="rejected",
    )

    session.add(
        approval,
    )
    session.commit()

    response = client.post(
        f"/concerts/{concert.id}/submit",
        follow_redirects=False,
    )

    assert response.status_code == 303

    session.refresh(
        approval,
    )

    assert approval.status == "pending"


def test_missing_concert_cannot_be_submitted(
    client: TestClient,
) -> None:
    """A nonexistent concert cannot be submitted."""

    response = client.post(
        "/concerts/99999/submit",
    )

    assert response.status_code == 404
