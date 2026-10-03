"""
Description:
Test integracyjny usługi `postgres`: czy wyszukiwanie tekstowe w zbudowanym obrazie zachowuje się
tak, jak zakładają narzędzia `find_*_text`. Wymaga działającego stacku.

Prawda, której pilnuje ten plik, mieszka poza naszym kodem: w słowniku sjp.pl, w parserze
Postgresa i w poprawkach nakładanych przy budowaniu obrazu (`postgres/dictionary/build.sh`,
`postgres/initdb/10_text_search.sql`). Trzy drogi dopasowania, każda do czego innego:

| droga   | zapytanie SQL              | do czego                                     |
|---------|----------------------------|----------------------------------------------|
| słowa   | `@@ plainto_tsquery(...)`  | słowa kluczowe w dowolnej odmianie           |
| fraza   | `@@ phraseto_tsquery(...)` | cały komunikat, słowa w tej samej kolejności |
| podciąg | `ILIKE '%...%'`            | kod błędu albo jego fragment, dosłownie      |

Co się dzieje po drodze:

1. Jedno połączenie na cały plik liczy wynik każdego przypadku z tabeli `CASES` — słownik ładuje
   się raz na połączenie (około 0,6 s), więc połączenie na test wydłużałoby przebieg kilkanaście
   razy.
2. Test sparametryzowany po przypadkach porównuje wynik z oczekiwanym.

O czym pamiętać przy zmianach:

- Teksty są zmyślone, nigdy kopiowane z korpusu.
- Przypadek z oczekiwaniem `False` jest tak samo ważny jak z `True`: „widoczne" nie może znaleźć
  „niewidoczne", a fragment kodu sklejonego z kropkami nie znajduje się słowami — dlatego
  istnieje droga przez podciąg.
- Zapytania to SQL wprost przez sterownik, bo klient bazy w `api` powstaje z importem
  dokumentacji (p. 49); wtedy nazwa konfiguracji przechodzi do niego.
- Zmiana słownika wymaga przebudowy obrazu, a zmiana mapowania w `initdb/` — także odtworzenia
  wolumenu, bo skrypty startowe działają tylko na pustej bazie.
"""

import asyncio
from typing import NamedTuple

import asyncpg
import pytest

from tests.conftest import postgres_dsn

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]

# Konfiguracja wyszukiwania zakładana przez `postgres/initdb/10_text_search.sql`.
CONFIG = "pl_search"

# Nazwa konfiguracji idzie jako tekst rzutowany w zapytaniu: sterownik koduje parametr według
# typu, który zgłasza serwer, a `regconfig` zgłasza się jako liczba.
WORDS     = "SELECT to_tsvector($1::text::regconfig, $2) @@ plainto_tsquery($1::text::regconfig, $3)"
PHRASE    = "SELECT to_tsvector($1::text::regconfig, $2) @@ phraseto_tsquery($1::text::regconfig, $3)"
SUBSTRING = "SELECT $1::text ILIKE '%' || $2::text || '%'"

CONFIG_PRESENT = "SELECT count(*) FROM pg_ts_config WHERE cfgname = $1"


class Case(NamedTuple):
    """
    Description:
    Jeden przypadek: tekst w bazie, zapytanie, droga dopasowania i to, czy ma się znaleźć.
    """

    name:     str   # np. "odmiana: liczba mnoga"
    mode:     str   # "words" | "phrase" | "substring"
    text:     str   # np. "Nie można połączyć się z serwerami."
    query:    str   # np. "serwer"
    expected: bool  # czy zapytanie ma znaleźć tekst


CASES = (
    # --- odmiana przez słownik ---
    Case("odmiana: narzędnik",          "words", "Nie udało się skomunikować z serwerem.", "serwer",                 True),
    Case("odmiana: liczba mnoga",       "words", "Nie można połączyć się z serwerami.",    "serwer",                 True),
    Case("odmiana: dwa słowa",          "words", "Brak uprawnienia do kancelarii.",        "uprawnienie kancelaria", True),

    # --- przedrostek „nie-" zostaje przy słowie i słowo dalej się odmienia ---
    Case("nie-: twierdzenie ≠ zaprzeczenie", "words", "Sprawy są niewidoczne dla użytkownika.", "widoczne sprawy",    False),
    Case("nie-: zaprzeczenie ≠ twierdzenie", "words", "Sprawy są widoczne dla wszystkich.",     "niewidoczne sprawy", False),
    Case("nie-: zaprzeczenie w odmianie",    "words", "Sprawy są niewidoczne dla użytkownika.", "niewidoczna sprawa", True),

    # --- nazwy własne z `custom_words.txt` ---
    Case("nazwa: eNadawca", "words", "Wysyłka przez eNadawcę kończy się statusem W toku.", "eNadawca", True),
    Case("nazwa: ePUAP",    "words", "Dokument wysłany z ePUAPu wrócił bez UPP.",          "ePUAP",    True),
    Case("nazwa: Dokus",    "words", "W Dokusie konto jest aktywne.",                      "Dokus",    True),

    # --- wyraz z łącznikiem wchodzi do indeksu jako części ---
    Case("łącznik: e-Doręczenia", "words", "Nie przychodzą przesyłki z e-Doręczeń.", "e-Doręczenia", True),
    Case("łącznik: końcówka",     "words", "Brak uprawnienia w ePUAP-ie.",           "ePUAP",        True),

    # --- kody: cały kod znajduje się słowami, fragment sklejony interpunkcją — nie ---
    Case("kod: cały",               "words", "Błąd SQLSTATE[23000] przy zapisie pisma.",    "SQLSTATE[23000]",  True),
    Case("kod: fragment po kropce", "words", "java.lang.OutOfMemoryError: Java heap space", "OutOfMemoryError", False),

    # --- fraza: liczy się kolejność ---
    Case("fraza: cały komunikat", "phrase", "Komunikat: Nie udało się skomunikować z serwerem.", "nie udało się skomunikować z serwerem", True),
    Case("fraza: inna kolejność", "phrase", "Z serwerem udało się skomunikować po restarcie.",   "skomunikować z serwerem",               False),

    # --- podciąg: to, czego słowa nie znajdują ---
    Case("podciąg: fragment po kropce", "substring", "java.lang.OutOfMemoryError: Java heap space", "OutOfMemoryError", True),
    Case("podciąg: sam numer",          "substring", "Baza zwraca ORA-00942 przy raporcie.",        "00942",            True),
    Case("podciąg: wielkość liter",     "substring", "BŁĄD ŁĄCZA z bazą danych.",                   "błąd łącza",       True),
)


async def _matches(
    connection: asyncpg.Connection,  # otwarte połączenie z bazą na stacku
    case:       Case,                # np. Case("odmiana: narzędnik", "words", "…", "serwer", True)
) -> bool:
    """
    Description:
    Odpowiada, czy zapytanie przypadku znajduje jego tekst drogą, którą przypadek wskazuje.

    Example args:
        connection=<asyncpg.Connection>
        case=Case("odmiana: narzędnik", "words", "Nie udało się … z serwerem.", "serwer", True)

    Example result:
        True
    """
    # podciąg nie korzysta ze słownika, więc nie dostaje nazwy konfiguracji
    if case.mode == "substring":
        return await connection.fetchval(SUBSTRING, case.text, case.query)

    # fraza wymaga tej samej kolejności słów
    if case.mode == "phrase":
        return await connection.fetchval(PHRASE, CONFIG, case.text, case.query)

    # słowa: wszystkie muszą wystąpić, w dowolnej kolejności i odmianie
    return await connection.fetchval(WORDS, CONFIG, case.text, case.query)


async def _run_cases() -> dict[str, bool]:
    """
    Description:
    Liczy wynik każdego przypadku w jednym połączeniu. Najpierw sprawdza, że konfiguracja
    wyszukiwania w ogóle istnieje: baza z wolumenu założonego przed dodaniem skryptów startowych
    odpowiada, ale konfiguracji nie ma, i bez tego sprawdzenia każdy przypadek padałby błędem,
    który nie mówi, co naprawić.

    Example args:
        (brak)

    Example result:
        {"odmiana: narzędnik": True, "nie-: twierdzenie ≠ zaprzeczenie": False, …}
    """
    connection = await asyncpg.connect(postgres_dsn())

    try:
        # --- konfiguracja z `initdb/` jest na miejscu ---
        present = await connection.fetchval(CONFIG_PRESENT, CONFIG)
        assert present == 1, (
            f"W bazie nie ma konfiguracji wyszukiwania `{CONFIG}`. Skrypty z `postgres/initdb/` "
            "działają tylko na pustym wolumenie — odtwórz wolumen `postgres_data`."
        )

        # --- przypadki ---
        outcomes = {case.name: await _matches(connection, case) for case in CASES}
    finally:
        await connection.close()

    return outcomes


@pytest.fixture(scope="module")
def outcomes() -> dict[str, bool]:
    """
    Description:
    Wyniki wszystkich przypadków, policzone raz na plik (`_run_cases()`).

    Example args:
        (brak)

    Example result:
        {"odmiana: narzędnik": True, "nie-: twierdzenie ≠ zaprzeczenie": False, …}
    """
    return asyncio.run(_run_cases())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_text_search_matches_what_the_tools_assume(
    case:     Case,             # np. Case("odmiana: narzędnik", "words", "…", "serwer", True)
    outcomes: dict[str, bool],  # np. {"odmiana: narzędnik": True, …}
) -> None:
    """Zapytanie daną drogą → tekst znaleziony albo nie, zgodnie z tabelą przypadków."""
    assert outcomes[case.name] is case.expected, (
        f"{case.mode}: zapytanie „{case.query}” wobec „{case.text}”"
    )
