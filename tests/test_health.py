from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_health_returns_ok(monkeypatch) -> None:
    class AvailableSession:
        def execute(self, statement) -> None:
            return None

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: AvailableSession())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    class UnavailableSession:
        def execute(self, statement) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setitem(
        app.dependency_overrides, get_db, lambda: UnavailableSession()
    )

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Base de données inaccessible"}
