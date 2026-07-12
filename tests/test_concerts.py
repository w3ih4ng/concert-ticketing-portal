from fastapi.testclient import TestClient


def test_create_concert(client: TestClient) -> None:
    """
    US07 — Create a concert event
      When an organiser POSTs a new concert
      Then it is created (201) and returned with an id
    """
    payload = {
        "title": "Rock Night",
        "date": "2026-08-01",
        "venue": "National Stadium",
        "organiser": "organiser1",
    }
    response = client.post("/concerts", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Rock Night"
    assert isinstance(body["id"], int)
