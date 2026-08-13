from fastapi.testclient import TestClient


def test_concerts_page_empty(client: TestClient) -> None:
    """The concerts page loads and shows an empty approved-concert state."""

    response = client.get("/")

    assert response.status_code == 200
    assert "No concerts found" in response.text
    assert "approved concerts" in response.text
