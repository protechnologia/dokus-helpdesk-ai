from collections.abc import Sequence
from datetime import date

from app.model.ticket_parsed import ParsedTicket
from app.tools.find_tickets_vector.base import FindTicketsVectorToolBase
from app.tools.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
    FoundTicket,
)


def default_tickets() -> list[FoundTicket]:
    """
    Description:
    Wbudowany zestaw atrapy: trzy zmyślone zgłoszenia o tym samym objawie („nie przychodzą
    przesyłki z e-Doręczeń") i trzech różnych przyczynach — najczęstszy kształt trafień w tym
    korpusie, na którym agent ma się nauczyć dopytywać zamiast zgadywać. Bez danych osobowych:
    treść jest wymyślona, nie skopiowana z korpusu.

    Example args:
        (brak)

    Example result:
        [FoundTicket(score=0.91, ticket=ParsedTicket(ticket_id="90001", …)), …]
    """
    common = {
        "component":                     "e-Doręczenia",
        "problem":                       "Nie przychodzą przesyłki z e-Doręczeń",
        "symptoms":                      "Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę",
        "error_codes":                   [],
        "resolution_vocabulary_version": 1,
    }

    tickets = [
        FoundTicket(score=0.91, ticket=ParsedTicket(
            **common,
            ticket_id         = "90001",
            date              = date(2026, 2, 10),
            cause             = "Zacięta kolejka pobierania po przerwanym połączeniu",
            solution          = "Zrestartowano kolejkę; zaległe przesyłki pobrały się same.",
            resolution        = "naprawione",
            questions_summary = "pytano, od kiedy brak przesyłek i czy dotyczy wszystkich skrzynek",
        )),
        FoundTicket(score=0.89, ticket=ParsedTicket(
            **common,
            ticket_id         = "90002",
            date              = date(2026, 4, 22),
            cause             = "Plik blokady pozostawiony po aktualizacji blokował pobieranie",
            solution          = "Usunięto plik blokady; po aktualizacji sprawdzić, czy nie wraca.",
            resolution        = "naprawione",
            questions_summary = "pytano, czy problem zaczął się po aktualizacji",
        )),
        FoundTicket(score=0.86, ticket=ParsedTicket(
            **common,
            ticket_id         = "90003",
            date              = date(2026, 6, 3),
            cause             = "Załącznik ponad limit operatora zatrzymał pobieranie skrzynki",
            solution          = "Przesyłkę z dużym załącznikiem odebrano ręcznie u operatora.",
            resolution        = "bez_zmian_w_systemie",
            questions_summary = "pytano o rozmiar załączników w ostatnich przesyłkach",
        )),
    ]

    return tickets


class FakeFindTicketsVectorTool(FindTicketsVectorToolBase):
    """
    Description:
    Atrapa `find_tickets_vector`: zamiast embeddera i Qdranta zwraca ustalony zestaw zgłoszeń,
    zawsze ten sam, ze stałymi id. Służy grafom na atrapach i testom, którym wystarczy wiedzieć, CO
    agent dostał, a nie jak zostało znalezione.

    Flow:
        1. Test (albo fabryka przy atrapach) tworzy ją z własnymi zgłoszeniami albo z zestawem
           wbudowanym; `dropped_below_threshold` pozwala odtworzyć wynik „próg wszystko wyciął".
        2. Każde `search()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `render_for_model()` i `cite()` pochodzą z klasy wspólnej z prawdziwym narzędziem.
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
            FakeFindTicketsVectorTool zwracająca wbudowane trzy zgłoszenia przy każdym wyszukaniu
        """
        self._result = FindTicketsVectorResult(
            items                   = list(tickets) if tickets is not None else default_tickets(),
            dropped_below_threshold = dropped_below_threshold,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindTicketsVectorQuery] = []

    async def search(
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
            FindTicketsVectorResult(items=[FoundTicket(score=0.91, …), …],
                                    dropped_below_threshold=0)
        """
        self.queries.append(query)

        return self._result
