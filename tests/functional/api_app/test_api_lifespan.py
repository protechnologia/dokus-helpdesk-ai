import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.parametrize(
    "closer",
    ["close_process_agent_tools", "close_process_anonymizer", "close_process_index_inspector"],
)
def test_shutting_the_app_down_closes_process_clients(
    monkeypatch: pytest.MonkeyPatch,
    closer:      str,
) -> None:
    """Sprawdza, czy wyłączenie aplikacji woła zamknięcie narzędzi agenta, anonimizatora i serwisu
    liczącego indeksy, każde dokładnie raz, dopiero po zakończeniu obsługi żądań.

    Wyłapuje aplikację, która przy wyłączaniu zostawia otwartą pulę połączeń z Postgresem,
    połączenia do embeddera i Qdranta, połączenia do usługi `anonymizer` albo połączenia
    serwisu trasy `GET /instance`."""
    closed: list[str] = []

    async def close() -> None:
        closed.append("closed")

    monkeypatch.setattr(f"app.main.{closer}", close)

    with TestClient(create_app()) as client:
        client.get("/health")

        assert closed == []

    assert closed == ["closed"]
