from collections.abc import Sequence
from datetime import date

from app.tools.tickets.find_tickets_text.base import FindTicketsTextToolBase
from app.tools.tickets.find_tickets_text.models import (
    FindTicketsTextQuery,
    FindTicketsTextResult,
    MatchedTicket,
)

# Dwa zmyślone wątki, już „po anonimizacji" ({KLIENT_1}). Tak leżą w tabeli wyszukiwania i tak
# dostaje je model: jeden tekst w kształcie `RawTicket.as_thread()`.
SIGNING_THREAD = "\n".join([
    "ZGŁOSZENIE 90011 z 2026-03-02",
    "Temat: Błąd przy podpisie",
    "",
    "OPIS ZGŁASZAJĄCEGO:",
    "Dzień dobry, przy podpisywaniu pisma z dużym załącznikiem (skan, ok. 40 MB) wyskakuje",
    "„Nie udało się skomunikować z serwerem”. Mniejsze pliki podpisują się bez problemu.",
    "Pozdrawiam, {KLIENT_1}",
    "",
    "KOMENTARZ 1 — konsultant, 2026-03-02 11:20:00 (typ: rozwiazanie):",
    "Podnieśliśmy limity zasobów serwera, podpis dużych plików już działa.",
])
NUMBERING_THREAD = "\n".join([
    "ZGŁOSZENIE 90012 z 2026-01-05",
    "Temat: Nie da się zapisać pisma",
    "",
    "OPIS ZGŁASZAJĄCEGO:",
    "Od 2 stycznia zapis pisma kończy się „Nie udało się skomunikować z serwerem”.",
    "W grudniu wszystko działało.",
    "",
    "KOMENTARZ 1 — konsultant, 2026-01-05 09:05:00 (typ: zwyczajny):",
    "Czy błąd pojawia się przy każdym rejestrze, czy tylko w kancelarii?",
    "",
    "KOMENTARZ 2 — klient, 2026-01-05 09:40:00 (typ: zwyczajny):",
    "Przy każdym.",
    "",
    "KOMENTARZ 3 — konsultant, 2026-01-05 10:15:00 (typ: rozwiazanie):",
    "Brakowało sekwencji numeracji na 2026 rok. Założyliśmy ją, zapis działa.",
])


def default_tickets() -> list[MatchedTicket]:
    """
    Description:
    Wbudowany zestaw atrapy: dwa zmyślone zgłoszenia z tym samym komunikatem na ekranie i dwiema
    różnymi przyczynami — tak wygląda w tym korpusie trafienie po dosłownym komunikacie: objaw
    już był, ale o przyczynie rozstrzyga kontekst czynności. Jedno znalezione po dosłownym
    komunikacie, drugie po słowach kluczowych. Oba to oryginalne wątki: przyczynę model wyczytuje
    z komentarza konsultanta, nie z gotowego pola. Treść jest wymyślona, nie skopiowana z korpusu.

    Example args:
        (brak)

    Example result:
        [MatchedTicket(matched_by="exact", ticket_id="90011", …), MatchedTicket(…, "90012", …)]
    """
    tickets = [
        MatchedTicket(
            matched_by = "exact",
            ticket_id  = "90011",
            date       = date(2026, 3, 2),
            subject    = "Błąd przy podpisie",
            thread     = SIGNING_THREAD,
        ),
        MatchedTicket(
            matched_by = "words",
            ticket_id  = "90012",
            date       = date(2026, 1, 5),
            subject    = "Nie da się zapisać pisma",
            thread     = NUMBERING_THREAD,
        ),
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
