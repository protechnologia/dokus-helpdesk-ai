"""
Description:
To, co wspólne dla prawdziwego `read_tickets_thread` i jego atrapy: nazwa, materiał, klasa
zapytania i lista źródeł (`cite()`). Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą
wątki (`search()`).

Przed — wynik odczytu:

    ReadTicketsThreadResult(threads=[TicketThread(
        ticket_id = "90011",
        date      = date(2026, 3, 2),
        subject   = "Błąd przy podpisie",
        thread    = "ZGŁOSZENIE 90011 z 2026-03-02\\nTemat: Błąd przy podpisie\\n…",
    )])

Po — tekst dla modelu:

    {
      "threads": [
        {
          "ticket_id": "90011",
          "date": "2026-03-02",
          "subject": "Błąd przy podpisie",
          "thread": "ZGŁOSZENIE 90011 z 2026-03-02\\nTemat: Błąd przy podpisie\\n\\nOPIS…"
        }
      ]
    }

O czym pamiętać przy zmianach:

- Wątek to jedno pole tekstowe: złamania linii stają się w JSON-ie `\\n`. Dzięki temu treść
  pisana przez klienta nie może udawać końca wyniku ani kolejnego zgłoszenia.
- Do modelu trafia wyłącznie tekst po anonimizacji — taki leży w tabeli wyszukiwania.
- Materiał jest ten sam co w `read_tickets_card` („tickets"), więc zgłoszenie odczytane jako
  karta i jako wątek trafia na listę źródeł raz.
- Tytułem źródła jest temat zgłoszenia, nie `problem` z karty: karty to narzędzie nie zna.
"""

from app.agent_tools.base import KnowledgeSource, read_description
from app.agent_tools.models import SourceRef
from app.agent_tools.tickets.read_tickets_thread.models import (
    ReadTicketsThreadQuery,
    ReadTicketsThreadResult,
    TicketThread,
)
from app.db_postgres.row.tickets import TicketRow


def thread_from_row(
    row: TicketRow,  # np. TicketRow(ticket_id="90011", subject="Błąd przy podpisie", …)
) -> TicketThread:
    """
    Description:
    Zamienia wiersz tabeli wyszukiwania na odczytany wątek, pole po polu. Wspólne dla atrapy
    i narzędzia właściwego: oba dostają wątki jako wiersze.

    Example args:
        row=TicketRow(ticket_id="90011", ticket_date=date(2026, 3, 2), subject="Błąd…", thread="…")

    Example result:
        TicketThread(ticket_id="90011", date=date(2026, 3, 2), subject="Błąd…", thread="…")
    """
    thread = TicketThread(
        ticket_id = row.ticket_id,
        date      = row.ticket_date,
        subject   = row.subject,
        thread    = row.thread,
    )

    return thread


class ReadTicketsThreadToolBase(KnowledgeSource):
    """
    Description:
    Wspólna część `read_tickets_thread`: wszystko poza samym pobraniem wątków.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeReadTicketsThreadTool`) i narzędzie właściwe na
    Postgresie (p. 56). Każda dokłada wyłącznie `search()`, więc tekst dla modelu i lista źródeł
    są te same w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `ReadTicketsThreadResult` albo zgłasza `UnknownTicketError`.
        2. `render_for_model()` z kontraktu robi z niego JSON.
        3. `cite()` robi z niego listę źródeł — po jednym wpisie na odczytany wątek.
    """

    name        = "read_tickets_thread"
    description = read_description(__file__)
    source      = "tickets"
    query_model = ReadTicketsThreadQuery

    def cite(
        self,
        result: ReadTicketsThreadResult,  # np. ReadTicketsThreadResult(threads=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każdy odczytany wątek; tytułem jest temat zgłoszenia.

        Example args:
            result=ReadTicketsThreadResult(threads=[TicketThread(ticket_id="90011", …)])

        Example result:
            [SourceRef(source="tickets", item_id="90011", title="Błąd przy podpisie",
                       date=date(2026, 3, 2))]
        """
        refs = [
            SourceRef(
                source  = self.source,
                item_id = thread.ticket_id,
                title   = thread.subject,
                date    = thread.date,
            )
            for thread in result.threads
        ]

        return refs
