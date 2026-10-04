"""
Description:
To, co wspólne dla prawdziwego `find_tickets_vector` i jego atrapy: nazwa, klasa argumentów
i tekst dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą wynik (`find()`).

Przed — wynik wyszukiwania:

    FindTicketsVectorResult(
        tickets = [
            FoundTicket(ticket_id="90001", score=0.91),
            FoundTicket(ticket_id="90002", score=0.89),
        ],
        dropped_below_threshold = 1,
    )

Po — tekst dla modelu:

    {
      "tickets": [
        {
          "ticket_id": "90001",
          "score": 0.91
        },
        {
          "ticket_id": "90002",
          "score": 0.89
        }
      ],
      "dropped_below_threshold": 1
    }

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: zwraca numery zgłoszeń, nie treść, i niczego nie cytuje. Źródłem
  odpowiedzi jest dopiero karta albo wątek, które model odczytał.
- Licznik odciętych progiem zostaje w wyniku — „nic nie było" i „próg wszystko wyciął" to dla
  agenta różne sytuacje.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.tickets.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
)


class FindTicketsVectorToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `find_tickets_vector`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą `FindTicketsVectorTool` (embedder i Qdrant) oraz
    `FakeFindTicketsVectorTool` (ustalony zestaw). Każda dokłada wyłącznie `find()`, więc tekst
    dla modelu jest ten sam w testach i na produkcji.

    Flow:
        1. `run()` woła `find()` podklasy i dostaje `FindTicketsVectorResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "find_tickets_vector"
    description = read_description(__file__)
    args_model  = FindTicketsVectorQuery

    @abstractmethod
    async def find(
        self,
        query: FindTicketsVectorQuery,  # np. FindTicketsVectorQuery(problem="Brak przesyłek", …)
    ) -> FindTicketsVectorResult:
        """
        Description:
        Znajduje zgłoszenia o problemie podobnym do zapytania, od najbardziej podobnego, już
        przycięte progiem.

        Example args:
            query=FindTicketsVectorQuery(problem="Nie przychodzą przesyłki z e-Doręczeń",
                                         symptoms="Brak nowych przesyłek w skrzynce")

        Example result:
            FindTicketsVectorResult(tickets=[FoundTicket(ticket_id="90001", score=0.91)],
                                    dropped_below_threshold=3)
        """

    async def run(
        self,
        args: FindTicketsVectorQuery,  # np. FindTicketsVectorQuery(problem="Brak przesyłek", …)
    ) -> str:
        """
        Description:
        Wyszukuje i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=FindTicketsVectorQuery(problem="Nie przychodzą przesyłki z e-Doręczeń",
                                        symptoms="Brak nowych przesyłek w skrzynce")

        Example result:
            {"tickets": [{"ticket_id": "90001", "score": 0.91}], "dropped_below_threshold": 3}
        """
        result = await self.find(args)
        text   = result_as_json(result)

        return text
