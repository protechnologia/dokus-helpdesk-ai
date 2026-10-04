from collections.abc import Sequence

from app.agent_tools.tickets.fake_tickets import default_threads
from app.agent_tools.tickets.read_tickets_thread.base import (
    ReadTicketsThreadToolBase,
    thread_from_row,
)
from app.agent_tools.tickets.read_tickets_thread.errors import UnknownTicketError
from app.agent_tools.tickets.read_tickets_thread.models import (
    ReadTicketsThreadQuery,
    ReadTicketsThreadResult,
)
from app.db_postgres.row.tickets import TicketRow


class FakeReadTicketsThreadTool(ReadTicketsThreadToolBase):
    """
    Description:
    Atrapa `read_tickets_thread`: zamiast Postgresa oddaje wątki ze zmyślonego zestawu wspólnego
    dla wszystkich atrap narzędzi zgłoszeń (`agent_tools/tickets/fake_tickets.py`). Inaczej niż
    atrapy wyszukiwań odpowiada NA TO, o co pytano — odczyt po numerze nie ma „zawsze tego samego
    wyniku".

    Flow:
        1. Test tworzy ją z własnymi wierszami tabeli albo z zestawem wbudowanym.
        2. Każde `search()` zapisuje zapytanie w `queries` i oddaje żądane wątki w kolejności
           żądania; nieznany numer kończy się `UnknownTicketError`, bez wyniku częściowego.
        3. `render_for_model()` i `cite()` pochodzą z kontraktu i z klasy wspólnej z prawdziwym
           narzędziem.
    """

    def __init__(
        self,
        rows: Sequence[TicketRow] | None = None,  # np. [TicketRow.from_thread("90011", …)]
    ):
        """
        Description:
        Ustala wątki, z których atrapa czyta, i zakłada dziennik zapytań.

        Example args:
            rows=None

        Example result:
            FakeReadTicketsThreadTool czytająca wbudowane pięć wątków
        """
        rows = list(rows) if rows is not None else default_threads()

        self._threads = {row.ticket_id: thread_from_row(row) for row in rows}

        # Publiczne celowo: testy sprawdzają, które wątki agent przeczytał.
        self.queries: list[ReadTicketsThreadQuery] = []

    async def search(
        self,
        query: ReadTicketsThreadQuery,  # np. ReadTicketsThreadQuery(ticket_ids=["90011"])
    ) -> ReadTicketsThreadResult:
        """
        Description:
        Zapisuje zapytanie i oddaje żądane wątki w kolejności żądania.

        Example args:
            query=ReadTicketsThreadQuery(ticket_ids=["90011"])

        Example result:
            ReadTicketsThreadResult(threads=[TicketThread(ticket_id="90011", …)])

        Raises:
            UnknownTicketError: któregoś numeru nie ma w bazie
        """
        self.queries.append(query)

        # --- wszystko albo nic: brak jednego wątku unieważnia cały odczyt ---
        unknown = [ticket_id for ticket_id in query.ticket_ids if ticket_id not in self._threads]

        if unknown:
            raise UnknownTicketError(unknown)

        result = ReadTicketsThreadResult(
            threads = [self._threads[ticket_id] for ticket_id in query.ticket_ids],
        )

        return result
