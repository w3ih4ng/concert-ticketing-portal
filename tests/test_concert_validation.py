from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from concert_portal.models import Concert


def _future_date(days: int = 30) -> str:
    """Return a valid future concert date."""

    return (date.today() + timedelta(days=days)).isoformat()


def _past_date() -> str:
    """Return yesterday's date."""

    return (date.today() - timedelta(days=1)).isoformat()


def test_api_trims_concert_text_fields(client: TestClient) -> None:
    """Valid concert text is trimmed before storage."""

    response = client.post(
        "/concerts",
        json={
            "title": "  Jazz Evening  ",
            "date": _future_date(),
            "venue": "  City Hall  ",
            "organiser": "  Music Events  ",
        },
    )

    assert response.status_code == 201

    body = response.json()
    assert body["title"] == "Jazz Evening"
    assert body["venue"] == "City Hall"
    assert body["organiser"] == "Music Events"


def test_api_rejects_whitespace_only_fields(
    client: TestClient,
    session: Session,
) -> None:
    """Whitespace-only required fields are rejected and not stored."""

    response = client.post(
        "/concerts",
        json={
            "title": "   ",
            "date": _future_date(),
            "venue": "   ",
            "organiser": "   ",
        },
    )

    assert response.status_code == 422

    errors = response.json()["detail"]
    assert errors["title"] == "Title is required."
    assert errors["venue"] == "Venue is required."
    assert errors["organiser"] == "Organiser is required."

    concerts = session.exec(select(Concert)).all()
    assert concerts == []


def test_api_rejects_past_concert_date(client: TestClient) -> None:
    """A concert date earlier than today is rejected."""

    response = client.post(
        "/concerts",
        json={
            "title": "Jazz Evening",
            "date": _past_date(),
            "venue": "City Hall",
            "organiser": "Music Events",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["date"] == ("Concert date cannot be earlier than today.")


def test_api_rejects_invalid_date_format(client: TestClient) -> None:
    """A malformed concert date is rejected."""

    response = client.post(
        "/concerts",
        json={
            "title": "Jazz Evening",
            "date": "31-12-2099",
            "venue": "City Hall",
            "organiser": "Music Events",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["date"] == "Enter a valid concert date."


def test_api_rejects_invalid_text_lengths(client: TestClient) -> None:
    """Concert text fields must remain within their length limits."""

    response = client.post(
        "/concerts",
        json={
            "title": "A",
            "date": _future_date(),
            "venue": "V" * 101,
            "organiser": "Music Events",
        },
    )

    assert response.status_code == 422

    errors = response.json()["detail"]
    assert errors["title"] == "Title must be at least 3 characters."
    assert errors["venue"] == "Venue must not exceed 100 characters."


def test_html_form_preserves_values_and_displays_errors(
    client: TestClient,
) -> None:
    """The form preserves valid values when another field is invalid."""

    response = client.post(
        "/concerts/new",
        data={
            "title": "  Jazz Evening  ",
            "date": _future_date(),
            "venue": "   ",
            "organiser": "  Music Events  ",
        },
    )

    assert response.status_code == 422
    assert "Venue is required." in response.text
    assert 'value="Jazz Evening"' in response.text
    assert 'value="Music Events"' in response.text


def test_html_form_rejects_past_date(client: TestClient) -> None:
    """The HTML form displays an error for a past concert date."""

    response = client.post(
        "/concerts/new",
        data={
            "title": "Jazz Evening",
            "date": _past_date(),
            "venue": "City Hall",
            "organiser": "Music Events",
        },
    )

    assert response.status_code == 422
    assert "Concert date cannot be earlier than today." in response.text


def test_html_form_saves_trimmed_values(
    client: TestClient,
    session: Session,
) -> None:
    """A valid form submission stores cleaned concert values."""

    response = client.post(
        "/concerts/new",
        data={
            "title": "  Jazz Evening  ",
            "date": _future_date(),
            "venue": "  City Hall  ",
            "organiser": "  Music Events  ",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    concert = session.exec(select(Concert)).one()
    assert concert.title == "Jazz Evening"
    assert concert.venue == "City Hall"
    assert concert.organiser == "Music Events"
