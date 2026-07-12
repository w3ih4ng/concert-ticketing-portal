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


def test_create_ticket(client: TestClient) -> None:
    """
    US15/16/17 — Create a ticket category with price and quantity
      When an organiser POSTs a ticket for a concert
      Then it is created (201) with category, price and quantity
    """
    concert_id = _create_concert(client)

    response = client.post(
        "/tickets",
        json={"concert_id": concert_id, "category": "VIP", "price": 250.0, "quantity": 100},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "VIP"
    assert body["price"] == 250.0
    assert body["quantity"] == 100
    assert body["sold"] == 0


def test_create_ticket_for_missing_concert(client: TestClient) -> None:
    """Creating a ticket for a non-existent concert returns 404."""
    response = client.post(
        "/tickets",
        json={"concert_id": 999, "category": "VIP", "price": 250.0, "quantity": 100},
    )
    assert response.status_code == 404


def test_list_tickets_for_concert(client: TestClient) -> None:
    """A concert's ticket categories can be listed."""
    concert_id = _create_concert(client)

    client.post(
        "/tickets",
        json={"concert_id": concert_id, "category": "VIP", "price": 250.0, "quantity": 100},
    )
    client.post(
        "/tickets",
        json={"concert_id": concert_id, "category": "Standard", "price": 100.0, "quantity": 500},
    )

    response = client.get(f"/concerts/{concert_id}/tickets")
    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) == 2
    assert {t["category"] for t in tickets} == {"VIP", "Standard"}
