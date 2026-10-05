"""
Description:
Test integracyjny usługi `postgres`: czy wyszukiwanie tekstowe w zbudowanym obrazie zachowuje się
tak, jak zakładają narzędzia `find_*_text`. Wymaga działającego stacku.

Prawda, której pilnuje ten plik, mieszka poza naszym kodem: w słowniku sjp.pl, w parserze
Postgresa i w poprawkach nakładanych przy budowaniu obrazu (`postgres/dictionary/build.sh`,
`postgres/initdb/10_text_search.sql`). Trzy drogi dopasowania, każda do czego innego:

| droga       | do czego                                     |
|-------------|----------------------------------------------|
| `words`     | słowa kluczowe w dowolnej odmianie           |
| `phrase`    | cały komunikat, słowa w tej samej kolejności |
| `substring` | kod błędu albo jego fragment, dosłownie      |

Co się dzieje po drodze:

1. Raz na cały plik teksty wszystkich przypadków z `CASES` trafiają do własnej tabeli testu,
   po wierszu na przypadek; identyfikatorem wiersza jest nazwa przypadku.
2. Dla każdego przypadku jego zapytanie szuka w tej tabeli drogą, którą przypadek wskazuje,
   a wynikiem jest to, czy wiersz TEGO przypadku jest wśród trafień.
3. Tabela jest kasowana, a test sparametryzowany po przypadkach porównuje wynik z oczekiwanym.

O czym pamiętać przy zmianach:

- Teksty są zmyślone, nigdy kopiowane z korpusu.
- Tabela jest własna (`text_search_stack_test`), nigdy tabela narzędzia — test ją zakłada
  i kasuje.
- Przypadek z oczekiwaniem `False` jest tak samo ważny jak z `True`: „widoczne" nie może znaleźć
  „niewidoczne", a fragment kodu sklejonego z kropkami nie znajduje się słowami — dlatego
  istnieje droga przez podciąg.
- SQL-a tu nie ma. Szuka `DocsTable` z `app/db_postgres/` — tymi samymi metodami, których użyją
  narzędzia `find_*_text`.
- Zmiana słownika wymaga przebudowy obrazu, a zmiana mapowania w `initdb/` — także odtworzenia
  wolumenu, bo skrypty startowe działają tylko na pustej bazie.
"""

import asyncio
from typing import NamedTuple

import pytest

from app.db_postgres import DocRow, DocsTable
from tests.conftest import build_postgres_client

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]

# Własna tabela testu: zakładana i kasowana tutaj, nigdy tabela, z której czyta narzędzie.
TEST_TABLE = "text_search_stack_test"


class Case(NamedTuple):
    """
    Description:
    Jeden przypadek: tekst w bazie, zapytanie, droga dopasowania i to, czy ma się znaleźć.
    """

    name:     str   # np. "odmiana: liczba mnoga"
    mode:     str   # metoda tabeli: "words" | "phrase" | "substring"
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
    Case("fraza: inna odmiana",   "phrase", "Komunikat: Nie udało się skomunikować z serwerem.", "nie udało się skomunikować z serwerami", True),
    Case("fraza: inna kolejność", "phrase", "Z serwerem udało się skomunikować po restarcie.",   "skomunikować z serwerem",               False),
    Case("fraza: brak słowa w środku", "phrase", "Komunikat: Nie udało się skomunikować z serwerem.", "nie udało skomunikować z serwerem", False),

    # --- podciąg: to, czego słowa nie znajdują ---
    Case("podciąg: fragment po kropce", "substring", "java.lang.OutOfMemoryError: Java heap space", "OutOfMemoryError", True),
    Case("podciąg: sam numer",          "substring", "Baza zwraca ORA-00942 przy raporcie.",        "00942",            True),
    Case("podciąg: wielkość liter",     "substring", "BŁĄD ŁĄCZA z bazą danych.",                   "błąd łącza",       True),

    # --- podciąg: `%` i `_` w zapytaniu są zwykłymi znakami, nie wzorcem ---
    Case("podciąg: % dosłownie",        "substring", "Wysyłka stanęła na 100% i zwróciła błąd.", "100%",              True),
    Case("podciąg: % to nie dowolny ciąg", "substring", "Błąd serwera aplikacji przy zapisie.",  "Błąd%aplikacji",    False),
    Case("podciąg: _ to nie dowolny znak", "substring", "Plik raport-2026.pdf nie otwiera się.", "raport_2026",       False),
)


def _row(
    case:    Case,  # np. Case("odmiana: narzędnik", "words", "Nie udało się … z serwerem.", "serwer", True)
    ordinal: int,   # miejsce przypadku w tabeli `CASES`
) -> DocRow:
    """
    Description:
    Wiersz tabeli dla jednego przypadku: tekst przypadku jako treść sekcji, a nazwa przypadku
    jako jej identyfikator. Tytuł jest stały, żeby szukanie trafiało wyłącznie po treści.

    Example args:
        case=Case("odmiana: narzędnik", "words", "Nie udało się … z serwerem.", "serwer", True)
        ordinal=0

    Example result:
        DocRow(section_id="odmiana: narzędnik", ordinal=0, body="Nie udało się…", …)
    """
    row = DocRow(
        section_id   = case.name,
        ordinal      = ordinal,
        document     = "Przypadki testu",
        version      = "1",
        chapter_path = "[]",
        title        = "-",
        description  = "-",
        body         = case.text,
    )

    return row


async def _run_cases() -> dict[str, bool]:
    """
    Description:
    Wypełnia własną tabelę tekstami przypadków i dla każdego sprawdza, czy jego zapytanie
    znajduje jego wiersz. Zakładanie tabeli potwierdza przy okazji, że baza ma konfigurację
    wyszukiwania — baza z wolumenu starszego niż skrypty startowe jej nie ma.

    Example args:
        (brak)

    Example result:
        {"odmiana: narzędnik": True, "nie-: twierdzenie ≠ zaprzeczenie": False, …}

    Raises:
        DbPostgresConfigError: w bazie nie ma konfiguracji wyszukiwania
    """
    client = build_postgres_client()
    table  = DocsTable(client, name=TEST_TABLE)

    try:
        # --- tabela od zera: wiersz na przypadek; `create()` sprawdza konfigurację z `initdb/` ---
        await table.drop()
        await table.create()
        await table.upsert([_row(case, ordinal) for ordinal, case in enumerate(CASES)])

        # --- każde zapytanie swoją drogą; szukanie oddaje identyfikatory wszystkich trafień ---
        outcomes = {}

        for case in CASES:
            found = await getattr(table, case.mode)(case.query)
            outcomes[case.name] = case.name in found

        await table.drop()
    finally:
        await client.aclose()

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
    """Sprawdza, czy wyszukiwanie tekstowe w bazie zachowuje się tak, jak zakładają narzędzia
    agenta. Każdy przypadek z tabeli `CASES` to zmyślony tekst zapisany w bazie, zapytanie i jedna
    z trzech dróg szukania (słowa, fraza albo podciąg); test porównuje, czy zapytanie znalazło
    ten tekst, z tym, co przypadek przewiduje — ma znaleźć wtedy, gdy powinno, i nie znaleźć, gdy
    nie powinno. Przypadki obejmują odmianę słów, zaprzeczenia z „nie-", nazwy własne, wyrazy
    z łącznikiem, kody błędów, kolejność słów we frazie oraz znaki `%` i `_` w zapytaniu.

    Wyłapuje obraz bazy, w którym polski słownik albo jego poprawki nie działają: wyszukiwanie
    dalej odpowiada, ale gubi albo dokłada trafienia — na przykład „widoczne" znajduje
    „niewidoczne", nazwa „eNadawca" nie znajduje się w odmianie, a fragmentu kodu błędu nie
    znajduje nawet szukanie podciągiem."""
    assert outcomes[case.name] is case.expected, (
        f"{case.mode}: zapytanie „{case.query}” wobec „{case.text}”"
    )
