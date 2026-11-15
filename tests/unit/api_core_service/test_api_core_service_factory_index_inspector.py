from collections.abc import Iterator

import pytest

from app.config import Settings
from app.core_service import factory_index_inspector
from app.core_service.factory_index_inspector import (
    build_index_inspector,
    close_process_index_inspector,
    get_index_inspector,
    process_index_inspector,
)
from app.core_service.inspector_indexes import IndexInspector
from tests._helpers.instance import scripted_inspector


@pytest.fixture(autouse=True)
def no_inspector_left_between_tests() -> Iterator[None]:
    """
    Description:
    Czyści serwis zapamiętany przez fabrykę przed testem i po nim: jest zapamiętywany na cały
    proces, więc bez tego jeden test dostawałby serwis zbudowany w innym.

    Example args:
        (brak)

    Example result:
        None — `process_index_inspector()` w teście buduje od nowa
    """
    process_index_inspector.cache_clear()

    yield

    process_index_inspector.cache_clear()


def test_the_inspector_is_built_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy dwa kolejne żądania dostają z zależności trasy ten sam serwis, a budowa
    jest wołana jeden raz.

    Wyłapuje serwis budowany na każde żądanie: każdy zakładałby nową pulę połączeń
    z Postgresem, który ładuje słownik w każdej sesji, więc każde `GET /instance` czekałoby na to
    około 0,6 s, a pule zostawałyby otwarte."""
    built: list[Settings] = []

    def build(settings: Settings) -> IndexInspector:
        built.append(settings)

        return scripted_inspector()

    monkeypatch.setattr(factory_index_inspector, "build_index_inspector", build)

    first  = get_index_inspector()
    second = get_index_inspector()

    assert len(built) == 1
    assert first is second


async def test_closing_closes_the_inspector_and_forgets_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy zamknięcie przy wyłączaniu aplikacji zamyka zbudowany serwis i zapomina go,
    więc następne użycie zbudowałoby nowy.

    Wyłapuje serwis pominięty przy zamykaniu (jego połączenia zostałyby otwarte) i serwis
    z zamkniętymi połączeniami, który dostałoby następne żądanie."""
    inspector = scripted_inspector()
    closed: list[str] = []

    async def aclose() -> None:
        closed.append("closed")

    monkeypatch.setattr(inspector, "aclose", aclose)
    monkeypatch.setattr(factory_index_inspector, "build_index_inspector", lambda s: inspector)

    process_index_inspector()
    await close_process_index_inspector()

    assert closed == ["closed"]
    assert process_index_inspector.cache_info().currsize == 0


async def test_closing_without_a_built_inspector_builds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy zamknięcie aplikacji, w której nikt nie zapytał o `GET /instance`, niczego
    nie buduje.

    Wyłapuje zamykanie, które najpierw buduje serwis, żeby go zamknąć: wyłączenie aplikacji bez
    konfiguracji baz kończyłoby się błędem, choć nikt baz nie używał."""
    def build(settings: Settings) -> IndexInspector:
        raise AssertionError("serwis nie powinien powstać przy zamykaniu")

    monkeypatch.setattr(factory_index_inspector, "build_index_inspector", build)

    await close_process_index_inspector()

    assert process_index_inspector.cache_info().currsize == 0


async def test_the_inspector_counts_the_configured_threads_table() -> None:
    """Sprawdza, czy stan instancji liczy wątki w tabeli o nazwie z `POSTGRES_TICKETS_TABLE`
    (tu `watki`), tej samej, w której szukają narzędzia.

    Wyłapuje tabelę zaszytą w kodzie: `GET /instance` pokazywałby pustą albo cudzą tabelę,
    a belka frontu mówiłaby o innym indeksie niż ten, z którego korzysta agent."""
    settings  = Settings(_env_file=None, postgres_password="x", postgres_tickets_table="watki")
    inspector = build_index_inspector(settings)

    try:
        assert inspector._tickets_threads.name == "watki"
    finally:
        await inspector.aclose()
