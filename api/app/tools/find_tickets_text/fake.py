from collections.abc import Sequence
from datetime import date

from app.model.ticket_parsed import ParsedTicket
from app.tools.find_tickets_text.base import FindTicketsTextToolBase
from app.tools.find_tickets_text.models import (
    FindTicketsTextQuery,
    FindTicketsTextResult,
    MatchedTicket,
)


def default_tickets() -> list[MatchedTicket]:
    """
    Description:
    Wbudowany zestaw atrapy: dwa zmyślone zgłoszenia z tym samym komunikatem na ekranie i dwiema
    różnymi przyczynami — tak wygląda w tym korpusie trafienie po dosłownym komunikacie: objaw
    już był, ale o przyczynie rozstrzyga kontekst czynności. Jedno znalezione po dosłownym
    komunikacie, drugie po słowach kluczowych. Treść jest wymyślona, nie skopiowana z korpusu.

    Example args:
        (brak)

    Example result:
        [MatchedTicket(matched_by="exact", ticket=ParsedTicket(ticket_id="90011", …)), …]
    """
    common = {
        "component":                     "główna aplikacja",
        "error_codes":                   ["Nie udało się skomunikować z serwerem"],
        "resolution_vocabulary_version": 1,
    }

    tickets = [
        MatchedTicket(matched_by="exact", ticket=ParsedTicket(
            **common,
            ticket_id         = "90011",
            date              = date(2026, 3, 2),
            problem           = "Błąd komunikacji z serwerem przy podpisywaniu pisma",
            symptoms          = "Przy podpisie pojawia się „Nie udało się skomunikować z serwerem”",
            cause             = "Limit zasobów serwera przekraczany przy podpisie dużych plików",
            solution          = "Dostawca podniósł limity zasobów; podpis dużych plików działa.",
            resolution        = "naprawione",
            questions_summary = "pytano o rozmiar podpisywanego pliku i porę wystąpienia błędu",
        )),
        MatchedTicket(matched_by="words", ticket=ParsedTicket(
            **common,
            ticket_id         = "90012",
            date              = date(2026, 1, 5),
            problem           = "Błąd komunikacji z serwerem przy rejestracji pisma",
            symptoms          = "Od początku roku zapis pisma kończy się błędem komunikacji",
            cause             = "Brak sekwencji numeracji na nowy rok",
            solution          = "Założono sekwencję numeracji na bieżący rok; zapis działa.",
            resolution        = "naprawione",
            questions_summary = "pytano, czy problem zaczął się z początkiem roku",
        )),
    ]

    return tickets


class FakeFindTicketsTextTool(FindTicketsTextToolBase):
    """
    Description:
    Atrapa `find_tickets_text`: zamiast Postgresa zwraca ustalony zestaw zgłoszeń, zawsze ten
    sam, ze stałymi id. Ta sama rola co `FakeFindTicketsVectorTool`.

    Flow:
        1. Test tworzy ją z własnymi zgłoszeniami albo z zestawem wbudowanym; `omitted_over_limit`
           pozwala odtworzyć wynik „zapytanie zbyt ogólne".
        2. Każde `search()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `render_for_model()` i `cite()` pochodzą z klasy wspólnej z prawdziwym narzędziem.
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
            FakeFindTicketsTextTool zwracająca wbudowane dwa zgłoszenia przy każdym wyszukaniu
        """
        self._result = FindTicketsTextResult(
            items              = list(tickets) if tickets is not None else default_tickets(),
            omitted_over_limit = omitted_over_limit,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindTicketsTextQuery] = []

    async def search(
        self,
        query: FindTicketsTextQuery,  # np. FindTicketsTextQuery(exact=["SQLSTATE[23000]"])
    ) -> FindTicketsTextResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindTicketsTextQuery(exact=["Nie udało się skomunikować z serwerem"])

        Example result:
            FindTicketsTextResult(items=[MatchedTicket(matched_by="exact", …), …],
                                  omitted_over_limit=0)
        """
        self.queries.append(query)

        return self._result
