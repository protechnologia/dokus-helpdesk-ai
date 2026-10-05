import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_shutting_the_app_down_closes_the_agent_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy wyłączenie aplikacji woła zamknięcie narzędzi agenta dokładnie raz, dopiero
    po zakończeniu obsługi żądań.

    Wyłapuje aplikację, która przy wyłączaniu zostawia otwartą pulę połączeń z Postgresem
    i połączenia do embeddera i Qdranta."""
    closed: list[str] = []

    async def close() -> None:
        closed.append("closed")

    monkeypatch.setattr("app.main.close_process_agent_tools", close)

    with TestClient(create_app()) as client:
        client.get("/health")

        assert closed == []

    assert closed == ["closed"]
