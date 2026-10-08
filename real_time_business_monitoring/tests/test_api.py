import pytest
from fastapi.testclient import TestClient

from api.main import app
from src import database

_ok, _ = database.check_connection()
pytestmark = pytest.mark.skipif(not _ok, reason="MySQL is not reachable (integration test)")

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_kpis_keys():
    body = client.get("/api/kpis").json()
    for key in ["transaction_count", "total_revenue", "anomaly_count", "revenue_at_risk"]:
        assert key in body


def test_transactions_and_alerts_are_lists():
    assert isinstance(client.get("/api/transactions", params={"limit": 5}).json(), list)
    assert isinstance(client.get("/api/alerts", params={"limit": 5}).json(), list)


def test_revenue_group_by_validation():
    assert client.get("/api/revenue", params={"group_by": "category"}).status_code == 200
    assert client.get("/api/revenue", params={"group_by": "nonsense"}).status_code == 400