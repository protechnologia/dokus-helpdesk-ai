from collections.abc import Sequence
from datetime import date

from app.model.ticket_parsed import ParsedTicket
from app.tools.base import KnowledgeSource
from app.tools.find_tickets.models import FindTicketsQuery, FindTicketsResult, FoundTicket
from app.tools.models import SourceRef


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

    return [
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


class FakeFindTickets(KnowledgeSource):
    """
    Description:
    Atrapa `find_tickets`: zamiast Qdranta i embeddera zwraca ustalony zestaw zgłoszeń, zawsze
    ten sam, ze stałymi id. Na niej chodzą grafy, zanim powstanie prawdziwe narzędzie (p. 9),
    i testy, którym wystarczy wiedzieć, CO agent dostał, a nie jak zostało znalezione.

    Flow:
        1. Test (albo fabryka przy atrapach) tworzy ją z własnymi zgłoszeniami albo z zestawem
           wbudowanym; `dropped_below_threshold` pozwala odtworzyć wynik „próg wszystko wyciął".
        2. Każde `search()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `render_for_model()` i `cite()` działają na wyniku jak w prawdziwym narzędziu.
    """

    name        = "find_tickets"
    query_model = FindTicketsQuery

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
            FakeFindTickets zwracająca wbudowane trzy zgłoszenia przy każdym wyszukaniu
        """
        self._result = FindTicketsResult(
            items                   = list(tickets) if tickets is not None else default_tickets(),
            dropped_below_threshold = dropped_below_threshold,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindTicketsQuery] = []

    async def search(
        self,
        query: FindTicketsQuery,  # np. FindTicketsQuery(problem="Nie przychodzą przesyłki", …)
    ) -> FindTicketsResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindTicketsQuery(problem="Nie przychodzą przesyłki", symptoms="pusta skrzynka")

        Example result:
            FindTicketsResult(items=[FoundTicket(score=0.91, …), …], dropped_below_threshold=0)
        """
        self.queries.append(query)

        return self._result

    def render_for_model(
        self,
        result: FindTicketsResult,  # np. FindTicketsResult(items=[…])
    ) -> str:
        """
        Description:
        Prosty tekst dla modelu: liczba trafień i po jednym bloku na zgłoszenie. Docelowy format
        (osobny blok przyczyn przed rekordami) powstaje w prawdziwym narzędziu (p. 18).

        Example args:
            result=FindTicketsResult(items=[FoundTicket(…)], dropped_below_threshold=0)

        Example result:
            "Znalezione zgłoszenia: 1 (odcięte progiem: 0)\\n\\n[90001] 2026-02-10 · e-Doręczenia …"
        """
        header = (
            f"Znalezione zgłoszenia: {len(result.items)} "
            f"(odcięte progiem: {result.dropped_below_threshold})"
        )

        blocks = [
            f"[{found.ticket.ticket_id}] {found.ticket.date.isoformat()} · "
            f"{found.ticket.component} · podobieństwo {found.score:.2f}\n"
            f"Problem: {found.ticket.problem}\n"
            f"Objawy: {found.ticket.symptoms}\n"
            f"Przyczyna: {found.ticket.cause}\n"
            f"Rozwiązanie: {found.ticket.solution}"
            for found in result.items
        ]

        return "\n\n".join([header, *blocks])

    def cite(
        self,
        result: FindTicketsResult,  # np. FindTicketsResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każde zgłoszenie z wyniku; tytułem jest `problem`.

        Example args:
            result=FindTicketsResult(items=[FoundTicket(score=0.91, ticket=ParsedTicket(…))])

        Example result:
            [SourceRef(source="find_tickets", item_id="90001", title="Nie przychodzą…", …)]
        """
        return [
            SourceRef(
                source  = self.name,
                item_id = found.ticket.ticket_id,
                title   = found.ticket.problem,
                score   = found.score,
                date    = found.ticket.date,
            )
            for found in result.items
        ]
