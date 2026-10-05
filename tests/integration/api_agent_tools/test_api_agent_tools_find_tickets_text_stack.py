"""
Description:
Test integracyjny narzędzia `find_tickets_text` z prawdziwym Postgresem: czy wątki zapisane
w tabeli zgłoszeń da się znaleźć po dosłownym brzmieniu i po słowach. Wymaga działającego stacku.

| scenariusz                                  | oczekiwanie                                  |
|---------------------------------------------|----------------------------------------------|
| komunikat z ekranu inną wielkością liter    | oba zgłoszenia, w których padł, jako `exact` |
| słowa w innej odmianie niż w wątku          | zgłoszenie znalezione słowami                |
| fraza i słowa trafiające w różne zgłoszenia | wszystkie, te z frazy pierwsze, każde raz    |
| fraza, którą mają trzy zgłoszenia           | od najnowszego, nie według numeru            |

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
    """Sprawdza, czy komunikat z ekranu wpisany inną wielkością liter niż w wątkach znajduje oba
    zgłoszenia, w których padł (90011 i 90012), oba oznaczone jako znalezione frazą.

    Wyłapuje wyszukiwanie dosłowne wrażliwe na wielkość liter albo oddające tylko część trafień:
    ten sam komunikat ma w tych zgłoszeniach dwie różne przyczyny, więc agent musi dostać oba,
    żeby je przeczytać i rozróżnić."""
    result = await tickets_threads.find.find(
        FindTicketsTextQuery(exact="nie udało się SKOMUNIKOWAĆ z serwerem")
    )

    assert [(found.ticket_id, found.matched_by) for found in result.tickets] == [
        ("90011", "exact"),
        ("90012", "exact"),
    ]
    assert result.omitted_over_limit == 0


async def test_words_in_another_form_find_the_ticket(tickets_threads) -> None:
    """Sprawdza, czy wyszukiwanie po słowach znajduje zgłoszenie, gdy słowa w zapytaniu mają inną
    odmianę i kolejność niż w wątku: „numeracja sekwencje" trafia w wątek ze zdaniem o brakującej
    sekwencji numeracji, i tylko w niego.

    Wyłapuje bazę bez polskiego słownika albo z zepsutą konfiguracją wyszukiwania: odmianę słów
    zna słownik bazy, nie nasz kod, więc bez niego agent musiałby trafić w dokładną formę słowa."""
    # "Brakowało sekwencji numeracji na 2026 rok."
    result = await tickets_threads.find.find(FindTicketsTextQuery(words="numeracja sekwencje"))

    assert [(found.ticket_id, found.matched_by) for found in result.tickets] == [
        ("90012", "words"),
    ]


async def test_a_phrase_and_words_bring_their_own_tickets(tickets_threads) -> None:
    """Sprawdza, czy fraza i słowa podane w jednym zapytaniu dają wspólny wynik bez powtórzeń:
    fraza pasuje do dwóch wątków, słowa „załącznik limit" do trzeciego, a zgłoszenia znalezione
    frazą stoją pierwsze. Zgłoszenie 90011 pasuje i do frazy, i do słów, a jest w wyniku raz,
    jako znalezione frazą.

    Wyłapuje błędne łączenie obu dróg wyszukiwania: zgłoszenie podwojone w wyniku, trafienia
    słowami przed trafieniami frazą albo zgubione trafienia jednej z dróg."""
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


async def test_tickets_found_by_a_phrase_come_newest_first(tickets_threads) -> None:
    """Sprawdza, czy zgłoszenia znalezione frazą wracają od najnowszego: fraza „e-Doręczeń" pasuje
    do trzech wątków, a wynik podaje je w kolejności czerwiec, kwiecień, luty, czyli odwrotnie
    niż według numeru.

    Wyłapuje zgubienie sortowania po dacie: gdy trafień jest więcej, niż mieści wynik, model ma
    zobaczyć najświeższe, bo nowsze zgłoszenie bywa poprawką starszego."""
    result = await tickets_threads.find.find(FindTicketsTextQuery(exact="e-Doręczeń"))

    assert [found.ticket_id for found in result.tickets] == ["90003", "90002", "90001"]
