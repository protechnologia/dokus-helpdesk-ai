"""
Description:
Wspólna mechanika tabel wyszukiwania tekstowego: kasowanie, odczyt i trzy drogi szukania. Po tej
klasie dziedziczą tabele materiałów (`TicketsTable`, `DocsTable`). Zakładanie tabeli i zapis
wierszy każda ma u siebie, jawnym SQL-em — tam widać jej kolumny i indeksy.

Umowa z tabelą konkretną. Każda tabela ma dwie kolumny wyliczane, o tych samych nazwach, i to
po nich szuka mechanika z tego pliku:

| kolumna         | co trzyma                                    | do czego          |
|-----------------|----------------------------------------------|-------------------|
| `search_text`   | złączone kolumny tekstowe tabeli             | podciąg (`ILIKE`) |
| `search_vector` | słowa tego tekstu po przejściu przez słownik | słowa i fraza     |

Trzy drogi szukania:

| metoda              | zapytanie                                    | przykład                 |
|---------------------|----------------------------------------------|--------------------------|
| `_find_words()`     | słowa kluczowe, dowolna kolejność i odmiana  | „załącznik limit"        |
| `_find_phrase()`    | cały komunikat, słowa w tej samej kolejności | „brak połączenia z bazą" |
| `_find_substring()` | dosłowny ciąg, bez względu na wielkość liter | „ORA-00942"              |

O czym pamiętać przy zmianach:

- Przeszukiwany tekst jest łączony RAZ, przy zapisie wiersza, nie przy zapytaniu. Zmierzone na
  1100 wierszach: łączenie i przepuszczanie przez słownik przy każdym zapytaniu trwa 4–5 s,
  z kolumną wyliczaną — 1–2 ms.
- Nazwa tabeli jest sprawdzana wzorcem przy budowie obiektu. Nie da się jej podać parametrem
  zapytania, więc to jedyna wartość z zewnątrz w treści SQL-a — nie może pochodzić od modelu.
  Nazwy kolumn pochodzą wyłącznie z klas tabel.
- Zapytanie agenta idzie zawsze parametrem. Przy podciągu przechodzi wcześniej przez
  `escape_like()`, bo `%` i `_` są we wzorcu znakami specjalnymi.
- Kody idą przez podciąg, bo parser pełnotekstowy skleja kod z interpunkcją w jeden token
  (`java.lang.outofmemoryerror`) i fragmentu kodu słowami nie znajdzie.
"""

import re
from collections.abc import Sequence

from app.db_postgres.client import PostgresClient
from app.db_postgres.errors import DbPostgresConfigError

# Konfiguracja wyszukiwania pełnotekstowego zakładana przez `postgres/initdb/10_text_search.sql`:
# polski słownik z poprawkami, a czego słownik nie zna (kody, nazwy własne spoza listy) — bez zmian.
TEXT_SEARCH_CONFIG = "pl_search"

# Dozwolona nazwa tabeli: małe litery, cyfry i podkreślenia, od litery, do 63 znaków (limit
# Postgresa). Wszystko inne to błąd, nie coś do unieszkodliwienia.
TABLE_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")

# Kolumny wyliczane, które każda tabela zakłada u siebie pod tymi nazwami.
SEARCH_TEXT   = "search_text"
SEARCH_VECTOR = "search_vector"

# Znak, którym w zapytaniu do podciągu poprzedza się `%`, `_` i samego siebie.
LIKE_ESCAPE = "\\"

CONFIG_PRESENT = "SELECT count(*) FROM pg_ts_config WHERE cfgname = $1"


def escape_like(
    text: str,  # np. "100%_gotowe"
) -> str:
    """
    Description:
    Unieszkodliwia znaki specjalne wzorca `ILIKE`, żeby zapytanie było szukane dosłownie: bez
    tego `_` znaczy „dowolny znak", a `%` — „dowolny ciąg".

    Example args:
        text="100%_gotowe"

    Example result:
        "100\\%\\_gotowe"
    """
    escaped = (
        text
        .replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)  # najpierw sam znak ucieczki
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )

    return escaped


class TextTable:
    """
    Description:
    Mechanika wspólna tabel wyszukiwania tekstowego: kasowanie, odczyt i szukanie.

    Do czego:
    Baza tabel materiałów. Z kolumn zna tylko dwie wyliczane, po których szuka; kolejność
    wyników i klucz tabeli dostaje od podklasy przy każdym wywołaniu. Kod spoza `app/db_postgres/`
    używa podklas (`TicketsTable`, `DocsTable`) i niczego poza nimi.

    Flow:
        1. Budowana z klienta i nazwy; zła nazwa to błąd od razu.
        2. Podklasa zakłada tabelę i zapisuje wiersze własnym SQL-em; przed zakładaniem woła
           `_require_search_config()`.
        3. `_find_words()`, `_find_phrase()` i `_find_substring()` szukają, `_read_by_id()`
           i `_list()` czytają — wszystkie oddają wiersze jako słowniki kolumna → wartość, bez
           kolumn wyliczanych, a na swój model zamienia je podklasa.
        4. `drop()` kasuje tabelę, `aclose()` zamyka jej klienta.
    """

    def __init__(
        self,
        client: PostgresClient,  # np. PostgresClient(host="postgres", …)
        name:   str,             # np. "docs_text"
    ):
        """
        Description:
        Zapamiętuje klienta i nazwę tabeli; z bazą się nie łączy.

        Example args:
            client=PostgresClient(host="postgres", port=5432, database="helpdesk", …)
            name="docs_text"

        Example result:
            TextTable „docs_text" w bazie helpdesk

        Raises:
            DbPostgresConfigError: nazwa spoza wzorca (wielkie litery, spacja, średnik, pusta…)
        """
        if not TABLE_NAME.fullmatch(name):
            raise DbPostgresConfigError(
                f"niedozwolona nazwa tabeli wyszukiwania: {name!r} — małe litery, cyfry "
                f"i podkreślenia, od litery"
            )

        self._client   = client
        self._name     = name
        self._sql_name = f'"{name}"'  # w cudzysłowie, gotowa do wstawienia w SQL

    @property
    def name(self) -> str:
        """
        Description:
        Nazwa tabeli, tak jak ją podano.

        Example args:
            (brak)

        Example result:
            "docs_text"
        """
        return self._name

    async def drop(self) -> None:
        """
        Description:
        Kasuje tabelę razem z indeksem. Brak tabeli nie jest błędem.

        Example args:
            (brak)

        Example result:
            None

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła polecenie
        """
        await self._client.execute(f"DROP TABLE IF EXISTS {self._sql_name}")

    async def aclose(self) -> None:
        """
        Description:
        Zamyka klienta, na którym stoi tabela — żeby ten, kto dostał samą tabelę, mógł po sobie
        posprzątać. Klient bywa wspólny dla kilku tabel; zamknięcie przez jedną zamyka go
        wszystkim, a powtórne zamknięcie nic nie robi.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._client.aclose()

    async def _require_search_config(self) -> None:
        """
        Description:
        Potwierdza, że baza ma konfigurację wyszukiwania `pl_search`. Zakładają ją skrypty
        z `postgres/initdb/`, a te działają tylko na pustym wolumenie — baza z wolumenu starszego
        niż skrypty odpowiada poprawnie, ale konfiguracji nie ma, i bez tego sprawdzenia
        zakładanie tabeli padałoby błędem serwera, który nie mówi, co naprawić.

        Example args:
            (brak)

        Example result:
            None — konfiguracja jest

        Raises:
            DbPostgresConfigError: w bazie nie ma konfiguracji `pl_search`
            DbPostgresError: baza nie odpowiada
        """
        present = await self._client.fetch_value(CONFIG_PRESENT, TEXT_SEARCH_CONFIG)

        if present != 1:
            raise DbPostgresConfigError(
                f"w bazie '{self._client.database}' nie ma konfiguracji wyszukiwania "
                f"'{TEXT_SEARCH_CONFIG}' — skrypty z `postgres/initdb/` działają tylko na pustym "
                f"wolumenie; odtwórz wolumen `postgres_data`"
            )

    async def _find_words(
        self,
        query: str,  # np. "uprawnienie kancelaria"
        limit: int,  # np. 5
        order: str,  # kolejność przy równym dopasowaniu, np. "section_id"
    ) -> list[dict[str, object]]:
        """
        Description:
        Znajduje wiersze zawierające wszystkie słowa zapytania — w dowolnej kolejności i odmianie,
        przez polski słownik. Najlepiej dopasowane pierwsze.

        Example args:
            query="uprawnienie kancelaria"
            limit=5
            order="section_id"

        Example result:
            [{"section_id": "adm-kancelaria-edoreczenia", "body": "Uprawnienie do kancelarii…", …}]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        tsquery = f"plainto_tsquery('{TEXT_SEARCH_CONFIG}', $1)"

        records = await self._find(
            condition = f"{SEARCH_VECTOR} @@ {tsquery}",
            order     = f"ts_rank({SEARCH_VECTOR}, {tsquery}) DESC, {order}",
            value     = query,
            limit     = limit,
        )

        return records

    async def _find_phrase(
        self,
        query: str,  # np. "nie udało się skomunikować z serwerem"
        limit: int,  # np. 5
        order: str,  # kolejność przy równym dopasowaniu, np. "ticket_id"
    ) -> list[dict[str, object]]:
        """
        Description:
        Znajduje wiersze zawierające słowa zapytania obok siebie, w tej samej kolejności — dla
        komunikatu przepisanego z ekranu. Odmiana nadal nie ma znaczenia.

        Example args:
            query="nie udało się skomunikować z serwerem"
            limit=5
            order="ticket_id"

        Example result:
            [{"ticket_id": "90011", "problem": "Błąd komunikacji z serwerem…", …}]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        tsquery = f"phraseto_tsquery('{TEXT_SEARCH_CONFIG}', $1)"

        records = await self._find(
            condition = f"{SEARCH_VECTOR} @@ {tsquery}",
            order     = f"ts_rank({SEARCH_VECTOR}, {tsquery}) DESC, {order}",
            value     = query,
            limit     = limit,
        )

        return records

    async def _find_substring(
        self,
        query: str,  # np. "ORA-00942"
        limit: int,  # np. 5
        order: str,  # kolejność wyników, np. "ticket_id"
    ) -> list[dict[str, object]]:
        """
        Description:
        Znajduje wiersze zawierające zapytanie dosłownie, bez względu na wielkość liter — dla
        kodu błędu albo jego fragmentu. Dopasowanie dosłowne nie ma stopnia, więc o kolejności
        decyduje wyłącznie `order`.

        Example args:
            query="ORA-00942"
            limit=5
            order="ticket_id"

        Example result:
            [{"ticket_id": "90014", "error_codes": "ORA-00942", …}]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._find(
            condition = f"{SEARCH_TEXT} ILIKE '%' || $1 || '%' ESCAPE '{LIKE_ESCAPE}'",
            order     = order,
            value     = escape_like(query),  # `%` i `_` mają być szukane dosłownie
            limit     = limit,
        )

        return records

    async def _read_by_id(
        self,
        key: str,            # kolumna klucza, np. "ticket_id"
        ids: Sequence[str],  # np. ["90011", "90012"]
    ) -> list[dict[str, object]]:
        """
        Description:
        Oddaje wiersze o podanych kluczach, w kolejności kluczy. Klucza, którego w tabeli nie ma,
        po prostu nie ma w wyniku — o tym, czy brak jest błędem, rozstrzyga wołający.

        Example args:
            key="ticket_id"
            ids=["90011", "90012"]

        Example result:
            [{"ticket_id": "90011", "problem": "…", "thread": "…"}, {"ticket_id": "90012", …}]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._client.fetch_rows(
            f"SELECT * FROM {self._sql_name} "
            f"WHERE {key} = ANY($1::text[]) ORDER BY array_position($1::text[], {key})",
            list(ids),
        )

        return [self._data(record) for record in records]

    async def _list(
        self,
        order: str,  # np. "document, version, ordinal"
    ) -> list[dict[str, object]]:
        """
        Description:
        Oddaje wszystkie wiersze tabeli w podanej kolejności.

        Example args:
            order="document, version, ordinal"

        Example result:
            [{"section_id": "adm-kancelaria-edoreczenia", "document": "Instrukcja…", …}, …]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._client.fetch_rows(
            f"SELECT * FROM {self._sql_name} ORDER BY {order}"
        )

        return [self._data(record) for record in records]

    async def _find(
        self,
        condition: str,  # np. "search_vector @@ plainto_tsquery('pl_search', $1)"
        order:     str,  # np. "section_id"
        value:     str,  # wartość parametru $1 — zapytanie agenta
        limit:     int,  # np. 5
    ) -> list[dict[str, object]]:
        """
        Description:
        Wykonuje jedno wyszukiwanie i oddaje wiersze do limitu. Warunek i kolejność przychodzą
        z metod tej klasy, nigdy od wołającego spoza niej.

        Example args:
            condition="search_text ILIKE '%' || $1 || '%' ESCAPE '\\'"
            order="section_id"
            value="00942"
            limit=5

        Example result:
            [{"section_id": "usr-komunikat-brak-serwera", "body": "Komunikat…", …}]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._client.fetch_rows(
            f"SELECT * FROM {self._sql_name} WHERE {condition} ORDER BY {order} LIMIT $2",
            value,
            limit,
        )

        return [self._data(record) for record in records]

    def _data(
        self,
        record: dict[str, object],  # np. {"section_id": "…", "body": "…", "search_text": "…", …}
    ) -> dict[str, object]:
        """
        Description:
        Zostawia w wierszu kolumny danych: dwie kolumny wyliczane służą do szukania i nie należą
        do wiersza, który oddajemy.

        Example args:
            record={"section_id": "adm-kancelaria-edoreczenia", "body": "…", "search_text": "…",
                    "search_vector": "'administrator':7 …"}

        Example result:
            {"section_id": "adm-kancelaria-edoreczenia", "body": "…"}
        """
        data = {
            column: value
            for column, value in record.items()
            if column not in (SEARCH_TEXT, SEARCH_VECTOR)
        }

        return data
