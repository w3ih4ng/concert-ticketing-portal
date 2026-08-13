from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import (
    Concert,
    ConcertApproval,
    ConcertPoster,
)
from concert_portal.web import UPLOAD_DIR


def _create_concert(
    session: Session,
    *,
    title: str,
    venue: str,
    date: str,
    status: str | None,
    organiser: str = "Test Events",
) -> Concert:
    """Create a concert with an optional approval status."""

    concert = Concert(
        title=title,
        date=date,
        venue=venue,
        organiser=organiser,
    )

    session.add(
        concert,
    )
    session.commit()
    session.refresh(
        concert,
    )

    assert concert.id is not None

    if status is not None:
        approval = ConcertApproval(
            concert_id=concert.id,
            status=status,
        )

        session.add(
            approval,
        )
        session.commit()

    return concert


def test_listing_shows_only_approved_concerts(
    client: TestClient,
    session: Session,
) -> None:
    """Public listing must exclude draft, pending and rejected concerts."""

    _create_concert(
        session,
        title="Approved Music Festival",
        venue="National Stadium",
        date="2030-08-01",
        status="approved",
    )

    _create_concert(
        session,
        title="Pending Concert",
        venue="Arena",
        date="2030-08-02",
        status="pending",
    )

    _create_concert(
        session,
        title="Rejected Concert",
        venue="Hall",
        date="2030-08-03",
        status="rejected",
    )

    _create_concert(
        session,
        title="Draft Concert",
        venue="Theatre",
        date="2030-08-04",
        status=None,
    )

    response = client.get(
        "/concerts",
    )

    assert response.status_code == 200

    assert "Approved Music Festival" in response.text

    assert "Pending Concert" not in response.text
    assert "Rejected Concert" not in response.text
    assert "Draft Concert" not in response.text


def test_listing_displays_name_date_and_venue(
    client: TestClient,
    session: Session,
) -> None:
    """Approved concert cards show the required basic details."""

    _create_concert(
        session,
        title="Summer Live",
        venue="Bukit Jalil Stadium",
        date="2030-06-15",
        status="approved",
    )

    response = client.get(
        "/concerts",
    )

    assert response.status_code == 200

    assert "Summer Live" in response.text
    assert "2030-06-15" in response.text
    assert "Bukit Jalil Stadium" in response.text


def test_listing_links_to_concert_details(
    client: TestClient,
    session: Session,
) -> None:
    """Each approved concert links to its detail page."""

    concert = _create_concert(
        session,
        title="Linked Concert",
        venue="Test Stadium",
        date="2030-09-01",
        status="approved",
    )

    assert concert.id is not None

    response = client.get(
        "/concerts",
    )

    assert response.status_code == 200

    assert f'href="/concerts/{concert.id}"' in response.text


def test_search_filters_by_title(
    client: TestClient,
    session: Session,
) -> None:
    """Attendees can search approved concerts by title."""

    _create_concert(
        session,
        title="Rock Universe",
        venue="Arena A",
        date="2030-10-01",
        status="approved",
    )

    _create_concert(
        session,
        title="Jazz Evening",
        venue="Arena B",
        date="2030-10-02",
        status="approved",
    )

    response = client.get(
        "/concerts",
        params={
            "search": "rock",
        },
    )

    assert response.status_code == 200

    assert "Rock Universe" in response.text
    assert "Jazz Evening" not in response.text


def test_search_filters_by_venue(
    client: TestClient,
    session: Session,
) -> None:
    """Search can also match a concert venue."""

    _create_concert(
        session,
        title="City Music",
        venue="National Stadium",
        date="2030-11-01",
        status="approved",
    )

    _create_concert(
        session,
        title="Hall Music",
        venue="Convention Centre",
        date="2030-11-02",
        status="approved",
    )

    response = client.get(
        "/concerts",
        params={
            "search": "national",
        },
    )

    assert response.status_code == 200

    assert "City Music" in response.text
    assert "Hall Music" not in response.text


def test_search_is_case_insensitive(
    client: TestClient,
    session: Session,
) -> None:
    """Search should not depend on letter casing."""

    _create_concert(
        session,
        title="Malaysia Live",
        venue="Stadium",
        date="2030-12-01",
        status="approved",
    )

    response = client.get(
        "/concerts",
        params={
            "search": "MALAYSIA",
        },
    )

    assert response.status_code == 200
    assert "Malaysia Live" in response.text


def test_filter_by_date(
    client: TestClient,
    session: Session,
) -> None:
    """Attendees can filter concerts by event date."""

    _create_concert(
        session,
        title="First Concert",
        venue="Arena",
        date="2030-07-10",
        status="approved",
    )

    _create_concert(
        session,
        title="Second Concert",
        venue="Arena",
        date="2030-07-20",
        status="approved",
    )

    response = client.get(
        "/concerts",
        params={
            "event_date": "2030-07-20",
        },
    )

    assert response.status_code == 200

    assert "Second Concert" in response.text
    assert "First Concert" not in response.text


def test_search_and_date_can_be_combined(
    client: TestClient,
    session: Session,
) -> None:
    """Both filters may be used together."""

    _create_concert(
        session,
        title="Rock One",
        venue="Arena",
        date="2030-05-01",
        status="approved",
    )

    _create_concert(
        session,
        title="Rock Two",
        venue="Arena",
        date="2030-05-02",
        status="approved",
    )

    response = client.get(
        "/concerts",
        params={
            "search": "rock",
            "event_date": "2030-05-02",
        },
    )

    assert response.status_code == 200

    assert "Rock Two" in response.text
    assert "Rock One" not in response.text


def test_no_matching_results_message(
    client: TestClient,
    session: Session,
) -> None:
    """A friendly message appears when filtering finds nothing."""

    _create_concert(
        session,
        title="Pop Concert",
        venue="Arena",
        date="2030-01-01",
        status="approved",
    )

    response = client.get(
        "/concerts",
        params={
            "search": "classical",
        },
    )

    assert response.status_code == 200

    assert "No concerts found" in response.text
    assert "No approved concerts match" in response.text


def test_listing_displays_poster(
    client: TestClient,
    session: Session,
) -> None:
    """Concert cards display the poster when one exists."""

    concert = _create_concert(
        session,
        title="Poster Concert",
        venue="Arena",
        date="2030-04-01",
        status="approved",
    )

    assert concert.id is not None

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = f"concert_{concert.id}_listing_test.png"

    path = UPLOAD_DIR / Path(filename).name

    path.write_bytes(b"\x89PNG\r\n\x1a\nlisting-test")

    poster = ConcertPoster(
        concert_id=concert.id,
        filename=filename,
    )

    session.add(
        poster,
    )
    session.commit()

    try:
        response = client.get(
            "/",
        )

        assert response.status_code == 200

        assert f'src="/concerts/{concert.id}/poster"' in response.text

        assert "Poster Concert" in response.text

    finally:
        if path.is_file():
            path.unlink()
