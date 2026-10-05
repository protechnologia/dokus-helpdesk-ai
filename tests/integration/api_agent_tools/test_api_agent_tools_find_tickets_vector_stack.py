"""
Description:
Test integracyjny narzędzia `find_tickets_vector` z prawdziwym embedderem i Qdrantem: czy karty
zapisane przez indeksację da się znaleźć po znaczeniu. Wymaga działającego stacku.

| scenariusz                                  | oczekiwanie                                  |
|---------------------------------------------|----------------------------------------------|
| pytanie polami zaindeksowanego zgłoszenia   | numer tego zgłoszenia pierwszy               |
| próg powyżej każdego możliwego podobieństwa | pusty wynik, komplet policzony jako odcięty  |

Indeks buduje fixture `tickets_cards` z `conftest.py` tego folderu: trzy zmyślone karty
zaindeksowane produkcyjnym `TicketsIndexer`.

O czym pamiętać przy zmianach:

- Asercje są na ranking, nigdy na wysokość score.
- Tryb embeddera, przestrzeń wektorów, liczenie progu i tłumaczenie błędów sprawdzają testy
  jednostkowe na podmienionym transporcie; trafność wyszukiwania to sprawa testów ewaluacyjnych.
"""

import pytest

from app.agent_tools.tickets.find_tickets_vector import (
    FindTicketsVectorQuery,
    FindTicketsVectorTool,
)

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


@pytest.mark.parametrize("position", [0, 1, 2], ids=["90001", "90002", "90003"])
async def test_a_ticket_asked_by_its_own_fields_comes_back_first(
    tickets_cards,
    position: int,
) -> None:
    """Sprawdza, czy zapytanie złożone z opisu problemu i objawów zaindeksowanej karty stawia jej
    numer na pierwszym miejscu — osobno dla każdej z trzech kart. Próg podobieństwa jest tu
    wyłączony, więc wracają wszystkie trzy numery i żaden nie jest liczony jako odcięty. Liczy
    się kolejność, nie wysokość podobieństwa.

    Wyłapuje rozjazd między indeksacją a wyszukiwaniem na prawdziwym embedderze i Qdrancie:
    gdyby karty zapisywano inaczej, niż się ich potem szuka, nawet pytanie słowami samej karty
    nie znalazłoby jej jako pierwszej."""
    card   = tickets_cards.cards[position]
    result = await tickets_cards.find.find(
        FindTicketsVectorQuery(problem=card.problem, symptoms=card.symptoms)
    )

    assert result.tickets[0].ticket_id    == card.ticket_id
    assert len(result.tickets)            == len(tickets_cards.cards)
    assert result.dropped_below_threshold == 0


async def test_a_threshold_nothing_passes_counts_everything_as_dropped(tickets_cards) -> None:
    """Sprawdza, czy przy progu podobieństwa ustawionym powyżej każdej możliwej wartości (1,1)
    wyszukiwanie nie oddaje żadnego zgłoszenia, ale liczy wszystkie trzy jako odcięte progiem.

    Wyłapuje zgubienie tego licznika: zbyt ostry próg wyglądałby wtedy dokładnie tak samo jak
    pusty indeks, a to dwie różne awarie."""
    card = tickets_cards.cards[0]
    tool = FindTicketsVectorTool(
        embedder  = tickets_cards.embedder,
        tickets   = tickets_cards.collection,
        top_k     = 5,
        score_min = 1.1,
    )

    result = await tool.find(FindTicketsVectorQuery(problem=card.problem, symptoms=card.symptoms))

    assert result.tickets                 == []
    assert result.dropped_below_threshold == len(tickets_cards.cards)
