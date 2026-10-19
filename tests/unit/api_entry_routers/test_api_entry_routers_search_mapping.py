import pytest

from app.agent_graphs import search
from app.entry_routers.search.mapping import (
    dropped_below_threshold,
    to_agent_queries,
    to_search_response,
)
from tests._helpers.routers.samples import (
    LOG,
    SEARCH_QUERIES,
    SOURCE,
    final_state,
    search_messages,
)

# Wynik narzędzia, z którego licznika odciętych progiem nie da się odczytać, i dlaczego.
WITHOUT_COUNTER = [
    pytest.param(None, id="wywołanie bez wyniku"),
    pytest.param('{"error": "przekroczono limit wywołań"}', id="błąd zamiast wyniku"),
    pytest.param('{"cards": [], "without_card": []}', id="narzędzie bez progu"),
    pytest.param("Znalezione zgłoszenia: 3", id="nie JSON"),
    pytest.param("[3]", id="JSON, ale nie obiekt"),
    pytest.param('{"dropped_below_threshold": "3"}', id="licznik nie jest liczbą"),
]


@pytest.mark.parametrize("result_text", WITHOUT_COUNTER)
def test_a_result_without_a_counter_gives_no_counter(
    result_text: str | None,  # wstrzykiwane przez pytest z listy WITHOUT_COUNTER wyżej
) -> None:
    """Sprawdza, czy z wyniku narzędzia, który licznika odciętych progiem nie niesie — brak wyniku,
    błąd, wynik narzędzia bez progu, tekst inny niż obiekt JSON albo licznik zapisany jako
    napis — nie wychodzi żaden licznik (`None`), a odczyt nie kończy się wyjątkiem.

    Wyłapuje odczyt, który na takim wyniku pada albo wpisuje zero: trasa kończyłaby się błędem
    serwera przy każdej turze uciętej limitem, a zero udawałoby wyszukanie, w którym próg niczego
    nie odciął."""
    assert dropped_below_threshold(result_text) is None


@pytest.mark.parametrize("count", [0, 3])
def test_the_counter_is_read_as_given_also_when_it_is_zero(
    count: int,  # wstrzykiwane przez pytest z listy w dekoratorze wyżej
) -> None:
    """Sprawdza, czy licznik odciętych progiem wraca z wyniku wyszukiwania dokładnie taki, jaki
    w nim stoi: 3 jako 3, a zero jako 0, nie jako brak licznika.

    Wyłapuje odczyt, który myli zero z brakiem: wołający nie odróżniłby wyszukania po znaczeniu,
    w którym próg niczego nie odciął, od narzędzia, które progu nie ma."""
    result_text = f'{{"tickets": [], "dropped_below_threshold": {count}}}'

    assert dropped_below_threshold(result_text) == count


def test_queries_come_from_the_knowledge_tools_in_call_order() -> None:
    """Sprawdza, czy z rozmowy grafu `search` wychodzą zapytania do narzędzi wiedzy w kolejności
    wywołań, z argumentami: dwa wyszukania, odczyt kart i wyszukanie z tury uciętej limitem, ale
    bez wywołania odpowiedzi `respond_search`.

    Wyłapuje zapytania, które gubią wywołanie albo dopisują wywołanie odpowiedzi: wołający nie
    widziałby, o co agent pytał, albo dostałby na liście uwagi jako zapytanie."""
    queries = to_agent_queries(search_messages())

    assert [query.tool for query in queries] == [query.tool for query in SEARCH_QUERIES]
    assert [query.arguments for query in queries] == [query.arguments for query in SEARCH_QUERIES]


def test_each_query_gets_the_counter_from_its_own_result() -> None:
    """Sprawdza, czy każde wyszukanie dostaje licznik odciętych progiem z wyniku swojego wywołania,
    także gdy wyniki dwóch wywołań z jednej tury wracają w odwrotnej kolejności: pierwsze 3,
    drugie 0, odczyt kart i wyszukanie bez wyniku — żadnego.

    Wyłapuje licznik dobrany po kolejności wiadomości zamiast po numerze wywołania: wołający
    przypisałby odcięte trafienia nie temu zapytaniu, a próg wyglądałby na zbyt ostry przy złym
    wyszukaniu."""
    queries = to_agent_queries(search_messages())

    assert [query.dropped_below_threshold for query in queries] == [3, 0, None, None]


def test_the_response_carries_the_run_of_the_graph() -> None:
    """Sprawdza, czy odpowiedź `/search` złożona ze stanu końcowego grafu niesie jego źródła, uwagi
    dla wdrożeniowca znak w znak, zapytania agenta z rozmowy, zużycie modelu i log przebiegu.

    Wyłapuje mapowanie, które gubi albo zastępuje wartością domyślną któreś pole stanu: każda
    droga, którą trasa oddaje wynik, złożyłaby wtedy odpowiedź bez tej części przebiegu."""
    notes = search.SearchNotes(internal_notes="## Zgłoszenia historyczne\n- 90001: kolejka")
    final = final_state(search, sources=[SOURCE], output=notes, messages=search_messages())

    response = to_search_response(final)

    assert [item.item_id for item in response.sources] == [SOURCE.item_id]
    assert response.internal_notes                     == notes.internal_notes
    assert response.queries                            == SEARCH_QUERIES
    assert response.usage.llm_calls                    == final.usage.calls
    assert [item.node for item in response.log]        == [entry.node for entry in LOG]
