"""
Description:
To, co wspólne dla prawdziwego `find_tickets_text` i jego atrapy: nazwa, materiał, klasa
zapytania, tekst dla modelu (`render_for_model()`) i lista źródeł (`cite()`). Narzędzie i atrapa
różnią się wyłącznie tym, skąd biorą wynik (`search()`).

Rekordy wyglądają dokładnie tak jak w `find_tickets_vector` (`tools/tickets/base.py`). Stąd
pochodzi nagłówek, informacja, czym zgłoszenie znaleziono, i wątek pod każdym rekordem:

    Znalezione zgłoszenia: 2 (pominięte ponad limit: 0)

    [90011] 2026-03-02 · dopasowanie: dosłowny ciąg
    component: główna aplikacja
    …
    --- wątek 90011 ---
    ZGŁOSZENIE 90011 z 2026-03-02
    …
    --- koniec wątku 90011 ---

O czym pamiętać przy zmianach:

- Materiał jest ten sam co w `find_tickets_vector` („tickets"), więc zgłoszenie znalezione obiema
  drogami trafia na listę źródeł raz.
- Źródło z tego narzędzia nie ma podobieństwa (`score=None`): dopasowanie dosłowne nie ma stopnia.
- Wątek stoi pod rekordem, bo szukamy w wątku, nie w rekordzie: dopasowanego ciągu może
  w rekordzie nie być, a model ma zobaczyć, gdzie padł.
"""

from app.tools.base import KnowledgeSource, read_description
from app.tools.models import SourceRef
from app.tools.tickets.base import render_ticket_record, render_ticket_thread
from app.tools.tickets.find_tickets_text.models import FindTicketsTextQuery, FindTicketsTextResult

# Etykiety dopasowania w tekście dla modelu.
MATCH_LABELS = {
    "exact": "dosłowny ciąg",
    "words": "słowa",
}


class FindTicketsTextToolBase(KnowledgeSource):
    """
    Description:
    Wspólna część `find_tickets_text`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeFindTicketsTextTool`) i narzędzie właściwe na Postgresie
    (p. 53). Każda dokłada wyłącznie `search()`, więc tekst dla modelu i lista źródeł są te same
    w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `FindTicketsTextResult`.
        2. `render_for_model()` robi z niego tekst: nagłówek i rekordy, każdy z wątkiem.
        3. `cite()` robi z niego listę źródeł — po jednym wpisie na rekord z tekstu.
    """

    name        = "find_tickets_text"
    description = read_description(__file__)
    source      = "tickets"
    query_model = FindTicketsTextQuery

    def render_for_model(
        self,
        result: FindTicketsTextResult,  # np. FindTicketsTextResult(items=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: nagłówek z licznikami i rekordy,
        a pod każdym rekordem wątek zgłoszenia. Bez trafień zostaje sam nagłówek.

        Example args:
            result=FindTicketsTextResult(items=[MatchedTicket(…)], omitted_over_limit=0)

        Example result:
            Znalezione zgłoszenia: 1 (pominięte ponad limit: 0)

            [90011] 2026-03-02 · dopasowanie: dosłowny ciąg
            component: główna aplikacja
            …
            --- wątek 90011 ---
            ZGŁOSZENIE 90011 z 2026-03-02
            …
            --- koniec wątku 90011 ---
        """
        header = (
            f"Znalezione zgłoszenia: {len(result.items)} "
            f"(pominięte ponad limit: {result.omitted_over_limit})"
        )

        records = [
            "\n".join([
                render_ticket_record(
                    matched.ticket,
                    f"dopasowanie: {MATCH_LABELS[matched.matched_by]}",
                ),
                render_ticket_thread(matched.ticket.ticket_id, matched.thread),
            ])
            for matched in result.items
        ]

        text = "\n\n".join([header, *records])

        return text

    def cite(
        self,
        result: FindTicketsTextResult,  # np. FindTicketsTextResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każde zgłoszenie z wyniku; tytułem jest `problem`, podobieństwa brak.

        Example args:
            result=FindTicketsTextResult(items=[MatchedTicket(matched_by="exact", ticket=…)])

        Example result:
            [SourceRef(source="tickets", item_id="90011", title="Błąd…", score=None, …)]
        """
        refs = [
            SourceRef(
                source  = self.source,
                item_id = matched.ticket.ticket_id,
                title   = matched.ticket.problem,
                score   = None,
                date    = matched.ticket.date,
            )
            for matched in result.items
        ]

        return refs
