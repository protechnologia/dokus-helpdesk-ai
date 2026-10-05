import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.find_tickets_text import FindTicketsTextQuery, MatchedTicket


def test_a_query_with_nothing_to_search_is_refused() -> None:
    """Sprawdza, czy zapytanie bez frazy (`exact`) i bez słów (`words`) kończy się wyjątkiem
    `ValidationError`.

    Wyłapuje wyszukiwanie puszczone bez niczego do szukania: oddałoby pustą listę, która wygląda
    jak „niczego takiego nie było"."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery()


@pytest.mark.parametrize(
    "arguments",
    [{"exact": "SQLSTATE[23000]"}, {"words": "załącznik limit"}],
    ids=["exact", "words"],
)
def test_one_field_is_enough(arguments: dict) -> None:
    """Sprawdza, czy zapytanie z samą frazą (`exact`) albo z samymi słowami (`words`) jest
    poprawne.

    Wyłapuje wymóg podania obu pól naraz: agent podaje to, co ma, na przykład sam kod błędu,
    i z jednym polem nie mógłby wtedy szukać."""
    assert FindTicketsTextQuery(**arguments)


def test_a_too_short_exact_text_is_refused() -> None:
    """Sprawdza, czy fraza do szukania dosłownego krótsza niż trzy znaki (tu „50") kończy się
    wyjątkiem `ValidationError`.

    Wyłapuje przyjęcie zbyt krótkiej frazy: „50" trafia w numery telefonów i daty, a takie
    przypadkowe trafienie wygląda na odpowiedź."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(exact="50")


def test_exact_takes_one_phrase_not_a_list() -> None:
    """Sprawdza, czy lista dwóch fraz podana w polu `exact` kończy się wyjątkiem
    `ValidationError`: jedno wywołanie to jedna fraza.

    Wyłapuje powrót do listy fraz: wynik nie mówiłby wtedy, która z nich trafiła."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(exact=["SQLSTATE[23000]", "ORA-00942"])


def test_an_unknown_argument_is_refused() -> None:
    """Sprawdza, czy argument, którego zapytanie nie przewiduje (tu `limit=20`), kończy się
    wyjątkiem `ValidationError`.

    Wyłapuje ciche pomijanie nieznanych argumentów: model sądziłby, że sam ustawił liczbę
    trafień, a decyduje o niej konfiguracja."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(words="załącznik", limit=20)


def test_a_matched_ticket_carries_no_content() -> None:
    """Sprawdza, czy znalezione zgłoszenie przyjmuje tylko numer i sposób dopasowania: próba
    dołożenia pola `thread` z treścią wątku kończy się wyjątkiem `ValidationError`.

    Wyłapuje wynik wyszukiwania, do którego ktoś dołożył wątek albo jego fragment: treść ma
    dawać wyłącznie odczyt, bo tylko on trafia na listę źródeł."""
    with pytest.raises(ValidationError):
        MatchedTicket(ticket_id="90011", matched_by="exact", thread="ZGŁOSZENIE 90011…")


def test_a_match_kind_outside_the_query_fields_is_refused() -> None:
    """Sprawdza, czy sposób dopasowania inny niż `exact` i `words` (tu `phrase`) kończy się
    wyjątkiem `ValidationError`.

    Wyłapuje etykietę, której model nie zna: sposób dopasowania ma nosić nazwę pola, którym
    agent sam pytał."""
    with pytest.raises(ValidationError):
        MatchedTicket(ticket_id="90011", matched_by="phrase")
