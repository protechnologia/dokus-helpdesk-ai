"""
Description:
Test integracyjny narzędzia `find_tickets_text` z prawdziwym Postgresem: czy wątki zapisane
w tabeli zgłoszeń da się znaleźć po dosłownym brzmieniu i po słowach. Wymaga działającego stacku.

| scenariusz                                  | oczekiwanie                                  |
|---------------------------------------------|----------------------------------------------|
| komunikat z ekranu inną wielkością liter    | oba zgłoszenia, w których padł, jako `exact` |
| słowa w innej odmianie niż w wątku          | zgłoszenie znalezione słowami                |
| fraza i słowa trafiające w różne zgłoszenia | wszystkie, te z frazy pierwsze, każde raz    |

Tabelę buduje fixture `tickets_threads` z `conftest.py` tego folderu: pięć zmyślonych wątków
z zestawu atrap.

O czym pamiętać przy zmianach:

- Łączenie dróg, etykiety i limit sprawdzają testy jednostkowe na kliencie-atrapie; tu zostaje
  to, co wie tylko baza: odmiana, wielkość liter i białe znaki.
- Na prawdziwych wątkach narzędzie ruszy dopiero po anonimizacji (p. 19) i masowym imporcie
  (p. 31); do tego czasu to jedyne sprawdzenie na bazie.
"""

import pytest

from app.agent_tools.tickets.find_tickets_text import FindTicketsTextQuery

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]


async def test_a_message_in_another_case_finds_every_ticket_it_was_in(tickets_threads) -> None:
    """Komunikat z ekranu inną wielkością liter → oba zgłoszenia, w których padł, jako `exact`:
    ten sam komunikat, dwie różne przyczyny — o tym, która, powiedzą dopiero odczyty."""
    result = await tickets_threads.find.find(
        FindTicketsTextQuery(exact="nie udało się SKOMUNIKOWAĆ z serwerem")
    )

    assert [(found.ticket_id, found.matched_by) for found in result.tickets] == [
        ("90011", "exact"),
        ("90012", "exact"),
    ]
    assert result.omitted_over_limit == 0


async def test_words_in_another_form_find_the_ticket(tickets_threads) -> None:
    """Słowa w innej odmianie i kolejności niż w wątku → zgłoszenie znalezione słowami: odmianę
    zna słownik bazy, nie nasz kod."""
    # "Brakowało sekwencji numeracji na 2026 rok."
    result = await tickets_threads.find.find(FindTicketsTextQuery(words="numeracja sekwencje"))

    assert [(found.ticket_id, found.matched_by) for found in result.tickets] == [
        ("90012", "words"),
    ]


async def test_a_phrase_and_words_bring_their_own_tickets(tickets_threads) -> None:
    """Fraza z dwóch wątków i słowa z trzeciego → trzy zgłoszenia, te z frazy pierwsze; 90011 ma
    i frazę, i oba słowa, a stoi raz, jako `exact`."""
    result = await tickets_threads.find.find(
        FindTicketsTextQuery(
            exact = "Nie udało się skomunikować z serwerem",
            words = "załącznik limit",
        )
    )

    assert [(found.ticket_id, found.matched_by) for found in result.tickets] == [
        ("90011", "exact"),
        ("90012", "exact"),
        ("90003", "words"),
    ]
