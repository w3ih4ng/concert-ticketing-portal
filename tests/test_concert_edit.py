from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import Concert


def _create_concert(
    session: Session,
) -> Concert:
    """Create a concert for edit tests."""

    concert = Concert(
        title="Original Concert",
        date="2030-08-01",
        venue="Original Venue",
        organiser="Original Organiser",
    )

    session.add(concert)
    session.commit()
    session.refresh(concert)

    return concert


def test_edit_concert_page_loads_existing_values(
    client: TestClient,
    session: Session,
) -> None:
    """The edit page displays the existing concert information."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.get(
        f"/concerts/{concert.id}/edit",
    )

    assert response.status_code == 200
    assert "Edit Concert" in response.text
    assert "Original Concert" in response.text
    assert "2030-08-01" in response.text
    assert "Original Venue" in response.text
    assert "Original Organiser" in response.text


def test_missing_concert_edit_page_returns_404(
    client: TestClient,
) -> None:
    """Editing a concert that does not exist returns 404."""

    response = client.get(
        "/concerts/99999/edit",
    )

    assert response.status_code == 404


def test_concert_can_be_updated(
    client: TestClient,
    session: Session,
) -> None:
    """Valid edited concert details are saved."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/edit",
        data={
            "title": "Updated Concert",
            "date": "2031-09-15",
            "venue": "Updated Stadium",
            "organiser": "Updated Organiser",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}/edit?updated=true")

    session.refresh(
        concert,
    )

    assert concert.title == "Updated Concert"
    assert concert.date == "2031-09-15"
    assert concert.venue == "Updated Stadium"
    assert concert.organiser == "Updated Organiser"


def test_edit_success_message_is_displayed(
    client: TestClient,
    session: Session,
) -> None:
    """The edit page displays the update success message."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.get(
        f"/concerts/{concert.id}/edit?updated=true",
    )

    assert response.status_code == 200
    assert "Concert details updated successfully." in response.text


def test_invalid_concert_update_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    """Invalid edit values are rejected without changing the concert."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/edit",
        data={
            "title": "",
            "date": "2020-01-01",
            "venue": "",
            "organiser": "",
        },
    )

    assert response.status_code == 422

    assert "Title cannot be blank." in response.text
    assert "Date cannot be in the past." in response.text
    assert "Venue cannot be blank." in response.text
    assert "Organiser cannot be blank." in response.text

    session.refresh(
        concert,
    )

    assert concert.title == "Original Concert"
    assert concert.date == "2030-08-01"
    assert concert.venue == "Original Venue"
    assert concert.organiser == "Original Organiser"


def test_edit_missing_concert_returns_404(
    client: TestClient,
) -> None:
    """Submitting an edit for a missing concert returns 404."""

    response = client.post(
        "/concerts/99999/edit",
        data={
            "title": "Updated Concert",
            "date": "2031-09-15",
            "venue": "Updated Stadium",
            "organiser": "Updated Organiser",
        },
    )

    assert response.status_code == 404


def test_concert_detail_contains_edit_link(
    client: TestClient,
    session: Session,
) -> None:
    """Concert details contain a link to the edit page."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.get(
        f"/concerts/{concert.id}",
    )

    assert response.status_code == 200
    assert f"/concerts/{concert.id}/edit" in response.text
    assert "Edit concert" in response.text
