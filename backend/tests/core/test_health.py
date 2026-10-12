import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.db import get_db
from app.main import app


class FakeSession:
    """Thay Session thật để test không cần PostgreSQL."""

    def __init__(self, db_down: bool) -> None:
        self.db_down = db_down

    def execute(self, statement: object) -> None:
        if self.db_down:
            raise OperationalError(str(statement), {}, Exception("db down"))


@pytest.mark.parametrize(
    ("db_down", "expected_db"),
    [(False, True), (True, False)],
    ids=["db-ok", "db-loi"],
)
def test_health_reports_api_and_db_status(
    client: TestClient, db_down: bool, expected_db: bool
) -> None:
    app.dependency_overrides[get_db] = lambda: FakeSession(db_down)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": expected_db}
