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

Każda oddaje IDENTYFIKATORY wszystkich pasujących wierszy, bez limitu i bez treści. Limit,
łączenie dróg i liczenie tego, co się nie zmieściło, należą do narzędzia; treść daje odczyt
(`_read_by_id()`).

Przed — wątek w `thread` i zapytanie agenta:

    …komunikat „Zaloguj się
    ponownie, aby kontynuować pracę"…        "Zaloguj się ponownie, aby kontynuować"

Po — `search_text`, w którym szuka podciąg: komunikat stoi w jednej linii, więc zapytanie go
znajduje:

    …komunikat „Zaloguj się ponownie, aby kontynuować pracę"…

O czym pamiętać przy zmianach:

- W `search_text` i w zapytaniu do podciągu każdy ciąg białych znaków, także twarda spacja,
  staje się jedną spacją (`WHITESPACE_RUN`). Po obu stronach liczy to baza tym samym wzorcem,
  więc „biały znak" znaczy to samo w tekście i w zapytaniu; ten sam wzorzec stoi w `_create.sql`
  każdej tabeli. Kolumna z treścią (`body`, `thread`) zostaje dosłowna.
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
- Szukanie nie ma limitu, bo oddaje same identyfikatory: nawet zapytanie pasujące do całego
  korpusu to kilkanaście kilobajtów, a narzędzie musi wiedzieć, ile wierszy pasowało w sumie.
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

# Ciąg białych znaków w rozumieniu bazy: `\s` i twarda spacja, której `\s` tu nie obejmuje
# (sprawdzone na obrazie usługi `postgres`), a która siedzi w co piętnastym zgłoszeniu. Ten sam
# wzorzec stoi w kolumnie `search_text` w `_create.sql` każdej tabeli.
WHITESPACE_RUN = r"[\s\u00A0]+"

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
        3. `_find_words()`, `_find_phrase()` i `_find_substring()` szukają i oddają klucze
           pasujących wierszy.
        4. `_read_by_id()` i `_list()` czytają: oddają wiersze jako słowniki kolumna → wartość,
           bez kolumn wyliczanych, a na swój model zamienia je podklasa.
        5. `drop()` kasuje tabelę, `aclose()` zamyka jej klienta.
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
        key:   str,  # kolumna klucza, np. "section_id"
    ) -> list[str]:
        """
        Description:
        Znajduje wiersze zawierające wszystkie słowa zapytania — w dowolnej kolejności i odmianie,
        przez polski słownik — i oddaje ich klucze. Najlepiej dopasowane pierwsze, przy równym
        dopasowaniu według klucza.

        Example args:
            query="uprawnienie kancelaria"
            key="section_id"

        Example result:
            ["adm-kancelaria-edoreczenia", "adm-kancelaria-epuap"]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        tsquery = f"plainto_tsquery('{TEXT_SEARCH_CONFIG}', $1)"

        keys = await self._find(
            key       = key,
            condition = f"{SEARCH_VECTOR} @@ {tsquery}",
            order     = f"ts_rank({SEARCH_VECTOR}, {tsquery}) DESC, {key}",
            value     = query,
        )

        return keys

    async def _find_phrase(
        self,
        query: str,  # np. "nie udało się skomunikować z serwerem"
        key:   str,  # kolumna klucza, np. "ticket_id"
    ) -> list[str]:
        """
        Description:
        Znajduje wiersze zawierające słowa zapytania obok siebie, w tej samej kolejności — dla
        komunikatu przepisanego z ekranu — i oddaje ich klucze. Odmiana nadal nie ma znaczenia.

        Example args:
            query="nie udało się skomunikować z serwerem"
            key="ticket_id"

        Example result:
            ["90011", "90012"]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        tsquery = f"phraseto_tsquery('{TEXT_SEARCH_CONFIG}', $1)"

        keys = await self._find(
            key       = key,
            condition = f"{SEARCH_VECTOR} @@ {tsquery}",
            order     = f"ts_rank({SEARCH_VECTOR}, {tsquery}) DESC, {key}",
            value     = query,
        )

        return keys

    async def _find_substring(
        self,
        query: str,  # np. "ORA-00942"
        key:   str,  # kolumna klucza, np. "ticket_id"
    ) -> list[str]:
        """
        Description:
        Znajduje wiersze zawierające zapytanie dosłownie, bez względu na wielkość liter — dla
        kodu błędu, nazwy opcji albo komunikatu — i oddaje ich klucze. Białe znaki zapytania
        baza sprowadza do pojedynczych spacji, tak jak w przeszukiwanym tekście. Dopasowanie
        dosłowne nie ma stopnia, więc o kolejności decyduje wyłącznie klucz.

        Example args:
            query="ORA-00942"
            key="ticket_id"

        Example result:
            ["90014"]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        needle = f"regexp_replace($1, '{WHITESPACE_RUN}', ' ', 'g')"

        keys = await self._find(
            key       = key,
            condition = f"{SEARCH_TEXT} ILIKE '%' || {needle} || '%' ESCAPE '{LIKE_ESCAPE}'",
            order     = key,
            value     = escape_like(query),  # `%` i `_` mają być szukane dosłownie
        )

        return keys

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
        key:       str,  # kolumna klucza, np. "section_id"
        condition: str,  # np. "search_vector @@ plainto_tsquery('pl_search', $1)"
        order:     str,  # np. "section_id"
        value:     str,  # wartość parametru $1 — zapytanie agenta
    ) -> list[str]:
        """
        Description:
        Wykonuje jedno wyszukiwanie i oddaje klucze wszystkich pasujących wierszy, w podanej
        kolejności. Klucz, warunek i kolejność przychodzą z metod tej klasy i z klas tabel,
        nigdy od wołającego spoza pakietu.

        Example args:
            key="section_id"
            condition="search_vector @@ plainto_tsquery('pl_search', $1)"
            order="section_id"
            value="uprawnienie"

        Example result:
            ["adm-kancelaria-edoreczenia", "adm-kancelaria-epuap"]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._client.fetch_rows(
            f"SELECT {key} FROM {self._sql_name} WHERE {condition} ORDER BY {order}",
            value,
        )

        return [str(record[key]) for record in records]

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
