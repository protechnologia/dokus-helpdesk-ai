from collections.abc import Sequence

from app.agent_tools.tickets.fake_tickets import default_threads
from app.agent_tools.tickets.read_tickets_thread.base import (
    ReadTicketsThreadToolBase,
    thread_from_row,
)
from app.agent_tools.tickets.read_tickets_thread.errors import UnknownTicketError
from app.agent_tools.tickets.read_tickets_thread.models import (
    ReadTicketsThreadQuery,
    TicketThread,
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
        2. Każde `search()` zapisuje zapytanie w `queries` i oddaje żądany wątek; nieznany numer
           kończy się `UnknownTicketError`.
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
        query: ReadTicketsThreadQuery,  # np. ReadTicketsThreadQuery(ticket_id="90011")
    ) -> TicketThread:
        """
        Description:
        Zapisuje zapytanie i oddaje żądany wątek.

        Example args:
            query=ReadTicketsThreadQuery(ticket_id="90011")

        Example result:
            TicketThread(ticket_id="90011", subject="Błąd przy podpisie", …)

        Raises:
            UnknownTicketError: numeru nie ma w bazie
        """
        self.queries.append(query)

        if query.ticket_id not in self._threads:
            raise UnknownTicketError(query.ticket_id)

        return self._threads[query.ticket_id]
