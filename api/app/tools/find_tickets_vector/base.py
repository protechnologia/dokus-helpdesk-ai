"""
Description:
To, co wspólne dla prawdziwego `find_tickets_vector` i jego atrapy: nazwa, materiał, klasa
zapytania, tekst dla modelu (`render_for_model()`) i lista źródeł (`cite()`). Narzędzie i atrapa
różnią się wyłącznie tym, skąd biorą wynik (`search()`), więc test na atrapie sprawdza ten sam
tekst, który model dostanie na produkcji.

Kształt rekordu — pola pod nazwami ze schematu — jest wspólny z `find_tickets_text` i opisany
z przykładem w `tools/render_tickets.py`. Stąd pochodzi tylko nagłówek i informacja, jak
zgłoszenie znaleziono:

    Znalezione zgłoszenia: 2 (odcięte progiem: 1)
    …
    [90001] 2026-02-10 · podobieństwo 0.91

O czym pamiętać przy zmianach:

- Nagłówek mówi, ile zgłoszeń znaleziono i ile odciął próg — „nic nie było" i „próg wszystko
  wyciął" to dla agenta różne sytuacje.
- Cytować wolno tylko to, co model zobaczył — `cite()` i `render_for_model()` chodzą po tych
  samych elementach wyniku.
"""

from app.tools.base import KnowledgeSource
from app.tools.find_tickets_vector.models import FindTicketsVectorQuery, FindTicketsVectorResult
from app.tools.models import SourceRef
from app.tools.render_tickets import render_found_tickets


class FindTicketsVectorToolBase(KnowledgeSource):
    """
    Description:
    Wspólna część `find_tickets_vector`: wszystko poza samym wyszukaniem.

    Do czego: Po tej klasie dziedziczą `FindTicketsVectorTool` (embedder i Qdrant) oraz
    `FakeFindTicketsVectorTool` (ustalony zestaw). Każda dokłada wyłącznie `search()`, więc tekst
    dla modelu i lista źródeł są te same w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `FindTicketsVectorResult`.
        2. `render_for_model()` robi z niego tekst: nagłówek i rekordy.
        3. `cite()` robi z niego listę źródeł — po jednym wpisie na rekord z tekstu.
    """

    name        = "find_tickets_vector"
    source      = "tickets"
    query_model = FindTicketsVectorQuery

    def render_for_model(
        self,
        result: FindTicketsVectorResult,  # np. FindTicketsVectorResult(items=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: nagłówek z licznikami i rekordy. Bez
        trafień zostaje sam nagłówek.

        Example args:
            result=FindTicketsVectorResult(items=[FoundTicket(…)], dropped_below_threshold=1)

        Example result:
            Znalezione zgłoszenia: 1 (odcięte progiem: 1)

            [90001] 2026-02-10 · podobieństwo 0.91
            component: e-Doręczenia
            …
        """
        header = (
            f"Znalezione zgłoszenia: {len(result.items)} "
            f"(odcięte progiem: {result.dropped_below_threshold})"
        )

        entries = [(found.ticket, f"podobieństwo {found.score:.2f}") for found in result.items]

        text = render_found_tickets(header, entries)

        return text

    def cite(
        self,
        result: FindTicketsVectorResult,  # np. FindTicketsVectorResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każde zgłoszenie z wyniku; tytułem jest `problem`.

        Example args:
            result=FindTicketsVectorResult(items=[FoundTicket(score=0.91, ticket=ParsedTicket(…))])

        Example result:
            [SourceRef(source="tickets", item_id="90001", title="Nie przychodzą…", …)]
        """
        refs = [
            SourceRef(
                source  = self.source,
                item_id = found.ticket.ticket_id,
                title   = found.ticket.problem,
                score   = found.score,
                date    = found.ticket.date,
            )
            for found in result.items
        ]

        return refs
