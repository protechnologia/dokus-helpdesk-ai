import pytest
from pydantic import ValidationError

from app.agent_tools.code.list_code_files import (
    DEFAULT_DEPTH,
    MAX_ENTRIES_PER_LISTING,
    ListCodeFilesQuery,
)

PATH = "src/lib/Urzad/Wysylka"


def test_a_query_without_arguments_asks_for_the_code_root() -> None:
    """Sprawdza, czy zapytanie bez argumentów jest poprawne i znaczy „katalog główny kodu,
    domyślna głębokość": ścieżki nie ma, a głębokość równa się stałej `DEFAULT_DEPTH`, czyli 2.

    Wyłapuje model zapytania, który wymaga ścieżki: model, który nie zna jeszcze układu kodu,
    nie miałby od czego zacząć i zgadywałby nazwę katalogu."""
    query = ListCodeFilesQuery()

    assert (query.path, query.depth) == (None, DEFAULT_DEPTH)
    assert DEFAULT_DEPTH == 2


def test_a_depth_larger_than_any_directory_is_not_refused() -> None:
    """Sprawdza, czy głębokość dużo większa, niż ma jakikolwiek katalog (tu 50), jest poprawnym
    zapytaniem.

    Wyłapuje górną granicę głębokości w walidacji zapytania: prośba o cały katalog kończyłaby
    się wtedy błędem i zużytą turą, a ma dać tyle poziomów, ile mieści limit pozycji."""
    query = ListCodeFilesQuery(path=PATH, depth=50)

    assert query.depth == 50


@pytest.mark.parametrize(
    "arguments",
    [
        {"path": PATH, "depth": 0},        # głębokość liczy się od 1
        {"path": PATH, "depth": -1},       # głębokość liczy się od 1
        {"path": ""},                      # pusta ścieżka; katalog główny to brak ścieżki
        {"path": PATH, "limit": 50},       # limit pozycji nie jest argumentem
        {"path": PATH, "recursive": True}, # argument spoza schematu
    ],
    ids=["głębokość zero", "głębokość ujemna", "pusta ścieżka", "limit", "nieznany argument"],
)
def test_malformed_arguments_are_refused(arguments: dict) -> None:
    """Sprawdza, czy głębokość mniejsza niż 1, pusta ścieżka i argumenty spoza schematu (`limit`,
    `recursive`) kończą się wyjątkiem `ValidationError`.

    Wyłapuje model zapytania, który przepuszcza takie argumenty: głębokość zero dałaby spis bez
    pozycji, a nieznany argument zostałby po cichu pominięty — model prosiłby o 50 pozycji
    i dostawał inną liczbę, niż zamówił."""
    with pytest.raises(ValidationError):
        ListCodeFilesQuery(**arguments)


def test_the_entry_limit_is_the_one_measured_on_the_real_code() -> None:
    """Sprawdza, czy limit pozycji jednego spisu (`MAX_ENTRIES_PER_LISTING`) wynosi 200.

    Wyłapuje obniżenie limitu bez ponownego pomiaru: przy 100 nie mieszczą się katalogi, które
    są listami modułów aplikacji (114–155 podkatalogów), czyli te, po które model sięga
    najpierw; zmiana ma być świadoma i razem z opisem dla modelu."""
    assert MAX_ENTRIES_PER_LISTING == 200
