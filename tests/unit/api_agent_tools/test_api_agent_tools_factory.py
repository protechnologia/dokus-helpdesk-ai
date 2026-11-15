import pytest

from app.agent_graphs import search
from app.agent_tools.factory import build_agent_tools
from app.config import Settings
from app.db_postgres import DbPostgresConfigError

# Konfiguracja z wartościami domyślnymi i hasłem bazy, którego w kodzie nie ma. Budowa narzędzi
# nie łączy się z niczym, więc test nie potrzebuje stacku.
SETTINGS = Settings(_env_file=None, postgres_password="helpdesk")


async def test_the_factory_builds_every_tool_in_the_order_of_the_graphs() -> None:
    """Sprawdza, czy fabryka narzędzi buduje z konfiguracji wszystkie narzędzia właściwe,
    w tej samej kolejności, w jakiej wymieniają je grafy z narzędziami wiedzy.

    Wyłapuje narzędzie pominięte przy budowie albo zastąpione atrapą oraz zmienioną kolejność:
    model dostaje definicje narzędzi w tej kolejności w każdej turze, a każde przestawienie
    unieważnia cache promptu."""
    tools = build_agent_tools(SETTINGS)

    assert [tool.name for tool in tools] == list(search.TOOL_NAMES)
    assert not any(type(tool).__name__.startswith("Fake") for tool in tools)

    for tool in tools:
        await tool.aclose()


async def test_every_built_tool_has_a_call_limit_in_the_configuration() -> None:
    """Sprawdza, czy każde narzędzie zbudowane przez fabrykę ma w konfiguracji limit wywołań
    i czy konfiguracja nie trzyma limitu narzędzia, którego fabryka nie buduje.

    Wyłapuje nowe narzędzie dopisane w jednym miejscu, a nie w drugim: graf z takim narzędziem
    nie dałby się złożyć, bo opis narzędzia obiecuje modelowi limit."""
    tools = build_agent_tools(SETTINGS)

    assert {tool.name for tool in tools} == set(SETTINGS.tool_call_limits())

    for tool in tools:
        await tool.aclose()


async def test_thread_tools_read_the_configured_table() -> None:
    """Sprawdza, czy oba narzędzia na wątkach zgłoszeń, `find_tickets_text`
    i `read_tickets_thread`, czytają tabelę o nazwie z `POSTGRES_TICKETS_TABLE` (tu `watki`).

    Wyłapuje narzędzie, które czyta tabelę zaszytą w kodzie: indeksacja pisałaby wątki do
    tabeli z konfiguracji, a agent szukałby w innej i dostawał puste wyniki."""
    settings = Settings(_env_file=None, postgres_password="x", postgres_tickets_table="watki")
    tools    = build_agent_tools(settings)
    by_name  = {tool.name: tool for tool in tools}

    try:
        assert by_name["find_tickets_text"]._tickets.name == "watki"
        assert by_name["read_tickets_thread"]._tickets.name == "watki"
    finally:
        for tool in tools:
            await tool.aclose()


def test_building_without_the_database_password_is_refused() -> None:
    """Sprawdza, czy fabryka narzędzi odmawia budowy, gdy konfiguracja nie ma hasła do bazy.

    Wyłapuje narzędzia zbudowane na niepełnej konfiguracji: błąd wyszedłby dopiero przy
    pierwszym wyszukaniu, w środku sprawy, za którą model już policzył tury."""
    with pytest.raises(DbPostgresConfigError):
        build_agent_tools(Settings(_env_file=None, postgres_password=None))
