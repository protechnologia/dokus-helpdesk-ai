"""
Description:
Atrapa klienta Postgresa dla testów narzędzi stojących na tabelach (`DocsTable`, `TicketsTable`).
Narzędzie dostaje w teście PRAWDZIWĄ tabelę, a podmieniony jest tylko klient — test sprawdza więc,
o co narzędzie pyta tabelę i co robi z jej odpowiedzią, bez bazy.

Klient rozpoznaje rodzaj zapytania po treści SQL-a i zapisuje je w `calls`:

| zapytanie tabeli | wpis w `calls`          | co oddaje                                        |
|------------------|-------------------------|--------------------------------------------------|
| `list_all()`     | `("list", None)`        | wszystkie wiersze, w kolejności podanej klientowi |
| `read_by_id()`   | `("read", [klucze])`    | wiersze o tych kluczach, w kolejności żądania    |
| `substring()`    | `("substring", fraza)`  | klucze ustalone dla tej frazy                    |
| `words()`        | `("words", słowa)`      | klucze ustalone dla tych słów                    |

Przykład — dwa zgłoszenia w tabeli, fraza trafia w jedno:

    client = ScriptedPostgres(
        key       = "ticket_id",
        rows      = [row.model_dump() for row in default_threads()],
        substring = {"ORA-00942": ["90011"]},
    )
    tool = FindTicketsTextTool(tickets=TicketsTable(client), limit=5)

    await tool.find(FindTicketsTextQuery(exact="ORA-00942"))

    client.calls  # [("substring", "ORA-00942")]

O czym pamiętać przy zmianach:

- Odczyt po kluczach pomija klucze, których w wierszach nie ma — tak jak baza. O tym, czy brak
  jest błędem, rozstrzyga narzędzie, i to jest przedmiotem testu.
- Że Postgres naprawdę tak dopasowuje i tak układa wiersze, sprawdzają testy na stacku.
- Treść SQL-a tabel sprawdza `test_api_db_postgres_tables.py`, na własnej atrapie zapisującej
  całe zapytania. Ta zna tylko tyle SQL-a, ile trzeba, żeby rozpoznać rodzaj zapytania.
- Plik, a nie `conftest.py`, z tego samego powodu co `helpers_transport.py`: atrapę bierze się
  jawnym importem, nie fixture'em.
"""

from collections.abc import Mapping, Sequence


class ScriptedPostgres:
    """
    Description:
    Klient bez bazy: na spis i odczyt oddaje podane wiersze, na podciąg i na słowa — ustalone
    klucze. Zapisuje każde zapytanie i to, czy został zamknięty.

    Do czego:
    Stoi w miejscu `PostgresClient` pod prawdziwą tabelą w testach jednostkowych narzędzi
    Postgresa. Ma te metody klienta, których tabela używa przy czytaniu i szukaniu.

    Flow:
        1. Test podaje kolumnę klucza, wiersze tabeli i odpowiedzi na frazy oraz słowa.
        2. `fetch_rows()` rozpoznaje rodzaj zapytania, dopisuje wpis do `calls` i odpowiada.
        3. Test sprawdza wynik narzędzia i `calls`.
    """

    database = "helpdesk"

    def __init__(
        self,
        key:       str,                                    # np. "ticket_id"
        rows:      Sequence[dict] = (),                    # np. [TicketRow(…).model_dump()]
        substring: Mapping[str, list[str]] | None = None,  # np. {"ORA-00942": ["90011"]}
        words:     Mapping[str, list[str]] | None = None,  # np. {"załącznik": ["90003"]}
    ):
        """
        Description:
        Ustala zawartość tabeli i odpowiedzi na wyszukiwania; zakłada dziennik zapytań.

        Example args:
            key="ticket_id"
            rows=[TicketRow.from_thread("90011", date(2026, 3, 2), "…").model_dump()]
            substring={"ORA-00942": ["90011"]}
            words=None

        Example result:
            ScriptedPostgres z jednym zgłoszeniem, odpowiadający nim na frazę „ORA-00942"
        """
        self._key       = key
        self._rows      = list(rows)
        self._substring = dict(substring or {})
        self._words     = dict(words or {})

        self.calls: list[tuple[str, object]] = []
        self.closed = False

    async def fetch_rows(
        self,
        sql:   str,     # np. 'SELECT ticket_id FROM "tickets_text" WHERE search_text ILIKE …'
        *args: object,  # np. ("ORA-00942",)
    ) -> list[dict]:
        """
        Description:
        Rozpoznaje rodzaj zapytania po treści SQL-a, zapisuje je i oddaje ustaloną odpowiedź.

        Example args:
            sql='SELECT ticket_id FROM "tickets_text" WHERE search_text ILIKE …'
            args=("ORA-00942",)

        Example result:
            [{"ticket_id": "90011"}]
        """
        # --- spis: jedyne zapytanie bez wartości ---
        if not args:
            self.calls.append(("list", None))

            return list(self._rows)

        value = args[0]

        # --- odczyt po kluczach: całe wiersze, w kolejności żądania, bez nieznanych ---
        if "ANY($1::text[])" in sql:
            self.calls.append(("read", value))

            by_key = {row[self._key]: row for row in self._rows}

            return [by_key[key] for key in value if key in by_key]

        # --- podciąg ---
        if "ILIKE" in sql:
            self.calls.append(("substring", value))

            return [{self._key: key} for key in self._substring.get(value, [])]

        # --- słowa przez słownik ---
        self.calls.append(("words", value))

        return [{self._key: key} for key in self._words.get(value, [])]

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje, że klient został zamknięty.

        Example args:
            (brak)

        Example result:
            None
        """
        self.closed = True
