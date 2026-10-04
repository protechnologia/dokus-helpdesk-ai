from collections.abc import Sequence

from app.agent_tools.tickets.find_tickets_text.base import FindTicketsTextToolBase
from app.agent_tools.tickets.find_tickets_text.models import (
    FindTicketsTextQuery,
    FindTicketsTextResult,
    MatchedTicket,
)


def default_matched() -> list[MatchedTicket]:
    """
    Description:
    Wbudowany wynik atrapy: dwa zgłoszenia z tym samym komunikatem na ekranie i dwiema różnymi
    przyczynami (`agent_tools/tickets/fake_tickets.py`) — tak wygląda w tym korpusie trafienie po
    dosłownym komunikacie: objaw już był, ale o przyczynie rozstrzyga kontekst czynności. Jedno
    znalezione po dosłownym ciągu, drugie po słowach kluczowych.

    Example args:
        (brak)

    Example result:
        [MatchedTicket(ticket_id="90011", matched_by="exact"), MatchedTicket(…, "words")]
    """
    matched = [
        MatchedTicket(ticket_id="90011", matched_by="exact"),
        MatchedTicket(ticket_id="90012", matched_by="words"),
    ]

    return matched


class FakeFindTicketsTextTool(FindTicketsTextToolBase):
    """
    Description:
    Atrapa `find_tickets_text`: zamiast Postgresa zwraca ustalone numery zgłoszeń, zawsze te
    same. Ta sama rola co `FakeFindTicketsVectorTool`.

    Flow:
        1. Test tworzy ją z własnymi numerami albo z zestawem wbudowanym; `omitted_over_limit`
           pozwala odtworzyć wynik „zapytanie zbyt ogólne".
        2. Każde `find()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        tickets:            Sequence[MatchedTicket] | None = None,  # np. [MatchedTicket(…)]
        omitted_over_limit: int = 0,                                # np. 35
    ):
        """
        Description:
        Ustala, co atrapa będzie zwracać, i zakłada dziennik zapytań.

        Example args:
            tickets=None
            omitted_over_limit=0

        Example result:
            FakeFindTicketsTextTool zwracająca wbudowane dwa numery przy każdym wyszukaniu
        """
        self._result = FindTicketsTextResult(
            tickets            = list(tickets) if tickets is not None else default_matched(),
            omitted_over_limit = omitted_over_limit,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindTicketsTextQuery] = []

    async def find(
        self,
        query: FindTicketsTextQuery,  # np. FindTicketsTextQuery(exact=["SQLSTATE[23000]"])
    ) -> FindTicketsTextResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindTicketsTextQuery(exact=["Nie udało się skomunikować z serwerem"])

        Example result:
            FindTicketsTextResult(tickets=[MatchedTicket(ticket_id="90011", matched_by="exact"), …],
                                  omitted_over_limit=0)
        """
        self.queries.append(query)

        return self._result
