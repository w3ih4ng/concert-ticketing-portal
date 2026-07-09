from fastapi.testclient import TestClient

from concert_portal.app import app

client = TestClient(app)


def test_health() -> None:
    """
    Scenario: API health check
      Given the API is running
      When I GET /health
      Then I receive 200 and {"status": "ok"}
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
