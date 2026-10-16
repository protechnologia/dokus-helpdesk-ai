import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.parametrize("closer", ["close_process_agent_tools", "close_process_anonymizer"])
def test_shutting_the_app_down_closes_process_clients(
    monkeypatch: pytest.MonkeyPatch,
    closer:      str,
) -> None:
    """Sprawdza, czy wyłączenie aplikacji woła zamknięcie narzędzi agenta i zamknięcie
    anonimizatora, każde dokładnie raz, dopiero po zakończeniu obsługi żądań.

    Wyłapuje aplikację, która przy wyłączaniu zostawia otwartą pulę połączeń z Postgresem,
    połączenia do embeddera i Qdranta albo połączenia do usługi `anonymizer`."""
    closed: list[str] = []

    async def close() -> None:
        closed.append("closed")

    monkeypatch.setattr(f"app.main.{closer}", close)

    with TestClient(create_app()) as client:
        client.get("/health")

        assert closed == []

    assert closed == ["closed"]
