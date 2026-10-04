"""
Description:
To, co wspólne dla prawdziwego `read_tickets_card` i jego atrapy: nazwa, materiał, klasa
zapytania, tekst dla modelu (`render_for_model()`) i lista źródeł (`cite()`). Narzędzie i atrapa
różnią się wyłącznie tym, skąd biorą karty (`search()`).

Przed — wynik odczytu:

    ReadTicketsCardResult(
        cards        = [ParsedTicket(ticket_id="90001", …)],
        without_card = ["90011"],
    )

Po — tekst dla modelu:

    {
      "cards": [
        {
          "ticket_id": "90001",
          "date": "2026-02-10",
          "component": "e-Doręczenia",
          "problem": "Nie przychodzą przesyłki z e-Doręczeń",
          "symptoms": "Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę",
          "error_codes": [],
          "cause": "Zacięta kolejka pobierania po przerwanym połączeniu",
          "solution": "Zrestartowano kolejkę; zaległe przesyłki pobrały się same.",
          "resolution": "naprawione",
          "questions_summary": "pytano, od kiedy brak przesyłek i czy dotyczy wszystkich skrzynek"
        }
      ],
      "without_card": [
        "90011"
      ]
    }

O czym pamiętać przy zmianach:

- Pola karty stoją pod nazwami ze schematu, bo prompty grafów odwołują się do nich po nazwie
  (`cause`, `solution`, `questions_summary`).
- `cause` zostaje w brzmieniu parsera, także gdy mówi „brak".
- Wersja słownika rozstrzygnięć jest w karcie dla nas, nie dla modelu — wycinamy ją z tekstu.
- Cytowane są tylko karty, które model dostał; numer z `without_card` nie jest źródłem.
- Materiał jest ten sam co w `read_tickets_thread` („tickets"), więc zgłoszenie odczytane jako
  karta i jako wątek trafia na listę źródeł raz.
"""

from app.agent_tools.base import KnowledgeSource, read_description, result_as_json
from app.agent_tools.models import SourceRef
from app.agent_tools.tickets.read_tickets_card.models import (
    ReadTicketsCardQuery,
    ReadTicketsCardResult,
)

# Pola karty, których model nie dostaje: metadane artefaktu, nie treść zgłoszenia.
HIDDEN_CARD_FIELDS = {"resolution_vocabulary_version"}


class ReadTicketsCardToolBase(KnowledgeSource):
    """
    Description:
    Wspólna część `read_tickets_card`: wszystko poza samym pobraniem kart.

    Do czego:
    Po tej klasie dziedziczą `ReadTicketsCardTool` (Qdrant) i `FakeReadTicketsCardTool` (ustalony
    zestaw). Każda dokłada wyłącznie `search()`, więc tekst dla modelu i lista źródeł są te same
    w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `ReadTicketsCardResult`.
        2. `render_for_model()` robi z niego JSON bez metadanych artefaktu.
        3. `cite()` robi z niego listę źródeł — po jednym wpisie na odczytaną kartę.
    """

    name        = "read_tickets_card"
    description = read_description(__file__)
    source      = "tickets"
    query_model = ReadTicketsCardQuery

    def render_for_model(
        self,
        result: ReadTicketsCardResult,  # np. ReadTicketsCardResult(cards=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: JSON z kartami i numerami bez karty,
        bez wersji słownika rozstrzygnięć.

        Example args:
            result=ReadTicketsCardResult(cards=[ParsedTicket(ticket_id="90001", …)])

        Example result:
            {"cards": [{"ticket_id": "90001", "problem": "…", "cause": "…", …}],
             "without_card": []}
        """
        text = result_as_json(result, exclude={"cards": {"__all__": HIDDEN_CARD_FIELDS}})

        return text

    def cite(
        self,
        result: ReadTicketsCardResult,  # np. ReadTicketsCardResult(cards=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każdą odczytaną kartę; tytułem jest `problem`.

        Example args:
            result=ReadTicketsCardResult(cards=[ParsedTicket(ticket_id="90001", …)])

        Example result:
            [SourceRef(source="tickets", item_id="90001", title="Nie przychodzą…",
                       date=date(2026, 2, 10))]
        """
        refs = [
            SourceRef(
                source  = self.source,
                item_id = card.ticket_id,
                title   = card.problem,
                date    = card.date,
            )
            for card in result.cards
        ]

        return refs
