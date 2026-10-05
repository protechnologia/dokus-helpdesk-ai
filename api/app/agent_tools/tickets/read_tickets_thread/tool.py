"""
Description:
Prawdziwe narzędzie `read_tickets_thread`: czyta z Postgresa oryginalny wątek zgłoszenia
o podanym numerze — w brzmieniu sprzed parsowania, po anonimizacji. Nie woła embeddera ani
LLM-a — tylko tabelę zgłoszeń.

    numer zgłoszenia → wiersz tabeli zgłoszeń → wątek z numerem, datą i tematem

Przed — zapytanie agenta:

    ReadTicketsThreadQuery(ticket_id="90012")

Po — wynik `search()`:

    TicketThread(
        ticket_id = "90012",
        date      = date(2026, 1, 5),
        subject   = "Nie da się zapisać pisma",
        thread    = "ZGŁOSZENIE 90012 z 2026-01-05\\nTemat: Nie da się zapisać pisma\\n…",
    )

Co się dzieje po drodze:

1. Tabela oddaje wiersz o tym numerze albo nic.
2. Gdy nie ma nic, odczyt kończy się `UnknownTicketError` z tym numerem.
3. Wiersz staje się wątkiem, pole po polu (`thread_from_row()`).

O czym pamiętać przy zmianach:

- Jedno wywołanie to jeden wątek, więc `AGENT_MAX_CALLS_READ_TICKETS_THREAD` jest wprost liczbą
  wątków, które model przeczyta w jednej sprawie. Kilka wątków to kilka wywołań; model może
  je zgłosić w jednej turze.
- Brak wątku to błąd, inaczej niż w `read_tickets_card`, gdzie brak karty jest stanem poprawnym.
- Wątek wraca z kolumny `thread`, czyli dosłowny, ze złamaniami linii i etykietami komentarzy.
  Tekst, w którym szuka `find_tickets_text`, ma białe znaki sprowadzone do spacji i do modelu
  nie idzie.
- Narzędzie nie skraca wątku: limit długości pojedynczego wątku czeka na prawdziwe wątki (p. 23).
- Numer znaleziony po karcie da się tu odczytać tylko wtedy, gdy tabela zgłoszeń ma to samo
  zgłoszenie — oba indeksy muszą powstawać z tego samego zestawu.
"""

import logging

from app.agent_tools.tickets.read_tickets_thread.base import (
    ReadTicketsThreadToolBase,
    thread_from_row,
)
from app.agent_tools.tickets.read_tickets_thread.errors import UnknownTicketError
from app.agent_tools.tickets.read_tickets_thread.models import (
    ReadTicketsThreadQuery,
    TicketThread,
)
from app.db_postgres import TicketsTable

logger = logging.getLogger(__name__)


class ReadTicketsThreadTool(ReadTicketsThreadToolBase):
    """
    Description:
    `read_tickets_thread` na prawdziwym indeksie: tabela zgłoszeń w Postgresie oddaje wiersz
    o podanym numerze, a narzędzie robi z niego wątek.

    Do czego:
    Źródło wiedzy agenta w grafach `search`, `suggest_questions` i `suggest_solution`: oryginalny
    wątek zgłoszenia znalezionego którymkolwiek wyszukiwaniem — dla szczegółu, którego karta nie
    niesie, i dla zgłoszeń bez karty. Tylko do odczytu.

    Flow:
        1. `search()` czyta wiersz po numerze zgłoszenia.
        2. Brak wiersza kończy odczyt `UnknownTicketError`.
        3. Wiersz staje się `TicketThread`.
        4. `render_for_model()` i `cite()` z klas bazowych robią z wyniku tekst i źródło.
    """

    def __init__(
        self,
        tickets: TicketsTable,  # np. TicketsTable(PostgresClient(host="postgres", …))
    ):
        """
        Description:
        Spina narzędzie z tabelą zgłoszeń. Tabela jest wstrzykiwana, nie budowana tutaj
        (zasada 4).

        Example args:
            tickets=TicketsTable(PostgresClient(host="postgres", port=5432, database="helpdesk", …))

        Example result:
            ReadTicketsThreadTool gotowe do odczytu z tabeli `tickets_text`
        """
        self._tickets = tickets

    async def search(
        self,
        query: ReadTicketsThreadQuery,  # np. ReadTicketsThreadQuery(ticket_id="90011")
    ) -> TicketThread:
        """
        Description:
        Czyta wątek zgłoszenia o podanym numerze.

        Example args:
            query=ReadTicketsThreadQuery(ticket_id="90011")

        Example result:
            TicketThread(ticket_id="90011", subject="Błąd przy podpisie", …)

        Raises:
            UnknownTicketError: numeru nie ma w bazie
            DbPostgresError: Postgres jest nieosiągalny albo odpowiedział błędem
        """
        rows = await self._tickets.read_by_id([query.ticket_id])

        # Same liczby: wątek to dane klienta.
        logger.info("read_tickets_thread found=%d", len(rows))

        if not rows:
            raise UnknownTicketError(query.ticket_id)

        return thread_from_row(rows[0])

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenie z Postgresem. Sprzątający woła tylko to i nie musi wiedzieć, z czego
        narzędzie jest zbudowane.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._tickets.aclose()
