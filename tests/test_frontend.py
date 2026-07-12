from fastapi.testclient import TestClient


def test_concerts_page_empty(client: TestClient) -> None:
    """The concerts page loads and shows an empty state."""
    response = client.get("/")
    assert response.status_code == 200
    assert "No concerts yet" in response.text


def test_create_concert_via_form(client: TestClient) -> None:
    """
    Submitting the HTML form creates a concert
    and it then appears on the concerts page.
    """
    response = client.post(
        "/concerts/new",
        data={
            "title": "Jazz Evening",
            "date": "2026-09-15",
            "venue": "City Hall",
            "organiser": "organiser1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Jazz Evening" in response.text
