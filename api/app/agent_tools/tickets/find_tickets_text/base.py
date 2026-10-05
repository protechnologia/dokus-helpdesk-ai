"""
Description:
To, co wspólne dla prawdziwego `find_tickets_text` i jego atrapy: nazwa, klasa argumentów
i tekst dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą wynik (`find()`).

Przed — wynik wyszukiwania:

    FindTicketsTextResult(
        tickets = [
            MatchedTicket(ticket_id="90011", matched_by="exact"),
            MatchedTicket(ticket_id="90012", matched_by="words"),
        ],
        omitted_over_limit = 0,
    )

Po — tekst dla modelu:

    {
      "tickets": [
        {
          "ticket_id": "90011",
          "matched_by": "exact"
        },
        {
          "ticket_id": "90012",
          "matched_by": "words"
        }
      ],
      "omitted_over_limit": 0
    }

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: zwraca numery zgłoszeń, nie treść, i niczego nie cytuje. Źródłem
  odpowiedzi jest dopiero wątek albo karta, które model odczytał.
- `matched_by` nosi nazwę pola, którym agent pytał: `exact` albo `words`.
- Numery są te same co w `find_tickets_vector`, więc zgłoszenie znalezione obiema drogami
  czyta się raz.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.tickets.find_tickets_text.models import (
    FindTicketsTextQuery,
    FindTicketsTextResult,
)


class FindTicketsTextToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `find_tickets_text`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeFindTicketsTextTool`) i narzędzie właściwe na Postgresie
    (`FindTicketsTextTool`). Każda dokłada wyłącznie `find()`, więc tekst dla modelu jest ten sam
    w testach i na produkcji.

    Flow:
        1. `run()` woła `find()` podklasy i dostaje `FindTicketsTextResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "find_tickets_text"
    description = read_description(__file__)
    args_model  = FindTicketsTextQuery

    @abstractmethod
    async def find(
        self,
        query: FindTicketsTextQuery,  # np. FindTicketsTextQuery(exact="SQLSTATE[23000]")
    ) -> FindTicketsTextResult:
        """
        Description:
        Znajduje zgłoszenia, których wątek zawiera dosłowne ciągi albo słowa z zapytania,
        dosłowne trafienia najpierw, przycięte limitem.

        Example args:
            query=FindTicketsTextQuery(exact="Nie udało się skomunikować z serwerem")

        Example result:
            FindTicketsTextResult(tickets=[MatchedTicket(ticket_id="90011", matched_by="exact")],
                                  omitted_over_limit=0)
        """

    async def run(
        self,
        args: FindTicketsTextQuery,  # np. FindTicketsTextQuery(words="załącznik limit")
    ) -> str:
        """
        Description:
        Wyszukuje i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=FindTicketsTextQuery(exact="Nie udało się skomunikować z serwerem")

        Example result:
            {"tickets": [{"ticket_id": "90011", "matched_by": "exact"}], "omitted_over_limit": 0}
        """
        result = await self.find(args)
        text   = result_as_json(result)

        return text
