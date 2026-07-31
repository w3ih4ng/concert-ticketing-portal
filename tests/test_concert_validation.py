from datetime import date, timedelta

from fastapi.testclient import TestClient

FUTURE_DATE = (date.today() + timedelta(days=30)).isoformat()
PAST_DATE = (date.today() - timedelta(days=1)).isoformat()


def _valid_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "title": "Rock Night",
        "date": FUTURE_DATE,
        "venue": "National Stadium",
        "organiser": "organiser1",
    }
    payload.update(overrides)
    return payload


# ---------- API (JSON) ----------


def test_create_concert_rejects_blank_title(client: TestClient) -> None:
    response = client.post("/concerts", json=_valid_payload(title="   "))
    assert response.status_code == 422
    assert "title" in response.json()["detail"]


def test_create_concert_rejects_blank_venue(client: TestClient) -> None:
    response = client.post("/concerts", json=_valid_payload(venue=""))
    assert response.status_code == 422
    assert "venue" in response.json()["detail"]


def test_create_concert_rejects_blank_organiser(client: TestClient) -> None:
    response = client.post("/concerts", json=_valid_payload(organiser="  "))
    assert response.status_code == 422
    assert "organiser" in response.json()["detail"]


def test_create_concert_rejects_too_long_title(client: TestClient) -> None:
    response = client.post("/concerts", json=_valid_payload(title="A" * 201))
    assert response.status_code == 422
    assert "title" in response.json()["detail"]


def test_create_concert_rejects_invalid_date(client: TestClient) -> None:
    response = client.post("/concerts", json=_valid_payload(date="not-a-date"))
    assert response.status_code == 422
    assert "date" in response.json()["detail"]


def test_create_concert_rejects_past_date(client: TestClient) -> None:
    response = client.post("/concerts", json=_valid_payload(date=PAST_DATE))
    assert response.status_code == 422
    assert "date" in response.json()["detail"]


def test_create_concert_trims_whitespace(client: TestClient) -> None:
    response = client.post("/concerts", json=_valid_payload(title="  Rock Night  "))
    assert response.status_code == 201
    assert response.json()["title"] == "Rock Night"


# ---------- HTML form ----------


def test_concert_form_rejects_blank_title(client: TestClient) -> None:
    response = client.post(
        "/concerts/new",
        data={"title": "   ", "date": FUTURE_DATE, "venue": "City Hall", "organiser": "org1"},
    )
    assert response.status_code == 422
    assert "cannot be blank" in response.text


def test_concert_form_preserves_valid_fields_on_error(client: TestClient) -> None:
    """If one field is invalid, the other entered values must still show in the re-rendered form."""
    response = client.post(
        "/concerts/new",
        data={"title": "   ", "date": FUTURE_DATE, "venue": "City Hall", "organiser": "org1"},
    )
    assert response.status_code == 422
    assert "City Hall" in response.text
    assert "org1" in response.text


def test_concert_form_rejects_past_date(client: TestClient) -> None:
    response = client.post(
        "/concerts/new",
        data={"title": "Jazz Night", "date": PAST_DATE, "venue": "City Hall", "organiser": "org1"},
    )
    assert response.status_code == 422
    assert "cannot be in the past" in response.text


def test_concert_form_trims_and_redirects_on_success(client: TestClient) -> None:
    response = client.post(
        "/concerts/new",
        data={
            "title": "  Jazz Night  ",
            "date": FUTURE_DATE,
            "venue": "City Hall",
            "organiser": "org1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    followed = client.get(response.headers["location"])
    assert "Jazz Night" in followed.text
