from collections.abc import Sequence

from app.agent_tools.tickets.find_tickets_vector.base import FindTicketsVectorToolBase
from app.agent_tools.tickets.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
    FoundTicket,
)


def default_found() -> list[FoundTicket]:
    """
    Description:
    Wbudowany wynik atrapy: trzy zgłoszenia o tym samym objawie i trzech różnych przyczynach
    (`agent_tools/tickets/fake_tickets.py`), z podobieństwami tak bliskimi, że nie da się po nich
    wybrać jednego — agent ma przeczytać wszystkie karty.

    Example args:
        (brak)

    Example result:
        [FoundTicket(ticket_id="90001", score=0.91), FoundTicket(ticket_id="90002", …), …]
    """
    found = [
        FoundTicket(ticket_id="90001", score=0.91),
        FoundTicket(ticket_id="90002", score=0.89),
        FoundTicket(ticket_id="90003", score=0.86),
    ]

    return found


class FakeFindTicketsVectorTool(FindTicketsVectorToolBase):
    """
    Description:
    Atrapa `find_tickets_vector`: zamiast embeddera i Qdranta zwraca ustalone numery zgłoszeń,
    zawsze te same. Służy grafom na atrapach i testom, którym wystarczy wiedzieć, CO agent dostał,
    a nie jak zostało znalezione.

    Flow:
        1. Test (albo fabryka przy atrapach) tworzy ją z własnymi numerami albo z zestawem
           wbudowanym; `dropped_below_threshold` pozwala odtworzyć wynik „próg wszystko wyciął".
        2. Każde `find()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        tickets:                 Sequence[FoundTicket] | None = None,  # np. [FoundTicket(…)]
        dropped_below_threshold: int = 0,                              # np. 3
    ):
        """
        Description:
        Ustala, co atrapa będzie zwracać, i zakłada dziennik zapytań.

        Example args:
            tickets=None
            dropped_below_threshold=0

        Example result:
            FakeFindTicketsVectorTool zwracająca wbudowane trzy numery przy każdym wyszukaniu
        """
        self._result = FindTicketsVectorResult(
            tickets                 = list(tickets) if tickets is not None else default_found(),
            dropped_below_threshold = dropped_below_threshold,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindTicketsVectorQuery] = []

    async def find(
        self,
        query: FindTicketsVectorQuery,  # np. FindTicketsVectorQuery(problem="Brak przesyłek", …)
    ) -> FindTicketsVectorResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindTicketsVectorQuery(problem="Nie przychodzą przesyłki",
                                         symptoms="pusta skrzynka")

        Example result:
            FindTicketsVectorResult(tickets=[FoundTicket(ticket_id="90001", score=0.91), …],
                                    dropped_below_threshold=0)
        """
        self.queries.append(query)

        return self._result
