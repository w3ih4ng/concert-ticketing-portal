from fastapi.testclient import TestClient


def _create_concert(client: TestClient) -> int:
    """Helper: create a concert and return its id."""
    response = client.post(
        "/concerts",
        json={
            "title": "Rock Night",
            "date": "2026-08-01",
            "venue": "National Stadium",
            "organiser": "organiser1",
        },
    )
    assert response.status_code == 201
    concert_id: int = response.json()["id"]
    return concert_id


def test_create_concert_form_redirects_to_detail(client: TestClient) -> None:
    """Creating a concert via the form lands on its detail page, ready to add tickets."""
    response = client.post(
        "/concerts/new",
        data={
            "title": "Jazz Evening",
            "date": "2026-09-15",
            "venue": "City Hall",
            "organiser": "organiser1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/concerts/")


def test_ticket_form_page_loads(client: TestClient) -> None:
    """US15/16/17 — The add-ticket form page loads for an existing concert."""
    concert_id = _create_concert(client)

    response = client.get(f"/concerts/{concert_id}/tickets/new")
    assert response.status_code == 200
    assert "Add Ticket Category" in response.text
    assert "Rock Night" in response.text


def test_ticket_form_page_missing_concert(client: TestClient) -> None:
    """The add-ticket form returns 404 for a concert that doesn't exist."""
    response = client.get("/concerts/999/tickets/new")
    assert response.status_code == 404


def test_create_ticket_via_form(client: TestClient) -> None:
    """
    US15/16/17 — Submitting the form creates the category with price and
    quantity, then redirects (303) back to the concert's detail page where
    the new category is visible with its availability.
    """
    concert_id = _create_concert(client)

    response = client.post(
        f"/concerts/{concert_id}/tickets/new",
        data={"category": "VIP", "price": "250.00", "quantity": "100"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/concerts/{concert_id}"

    followed = client.get(response.headers["location"])
    assert followed.status_code == 200
    assert "VIP" in followed.text
    assert "100 left" in followed.text


def test_create_ticket_via_form_missing_concert(client: TestClient) -> None:
    """Posting tickets for a missing concert redirects home with an error banner."""
    response = client.post(
        "/concerts/999/tickets/new",
        data={"category": "VIP", "price": "250.00", "quantity": "100"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/?error=concert_missing"

    followed = client.get(response.headers["location"])
    assert "That concert could not be found" in followed.text
