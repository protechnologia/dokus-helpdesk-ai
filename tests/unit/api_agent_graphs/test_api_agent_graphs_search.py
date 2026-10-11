import pytest
from pydantic import ValidationError

from app.agent_graphs import search
from app.agent_graphs.search import SearchNotes

# Wynik grafu `search` i to, czego w jego prompcie nie widać w diffie. Kształt grafu, narzędzia
# i zabezpieczenia wspólne dla wszystkich grafów sprawdza test kontraktu grafów.

# Nagłówki czterech sekcji uwag dla wdrożeniowca, w kolejności wzoru z promptu systemowego.
NOTE_HEADINGS = [
    "Zgłoszenia historyczne",
    "Instrukcje i dokumentacja",
    "Kod aplikacji",
    "Nie znaleziono",
]


def test_the_search_answer_must_carry_notes() -> None:
    """Sprawdza, czy odpowiedź wyszukiwania bez pola `internal_notes` daje błąd walidacji.

    Wyłapuje wyszukiwanie, które model może zakończyć bez uwag: wdrożeniowiec dostałby samą listę
    źródeł, na której sprawy o różnych przyczynach wyglądają tak samo jak zgodne."""
    with pytest.raises(ValidationError):
        SearchNotes.model_validate({})


def test_the_notes_of_a_search_may_not_be_empty() -> None:
    """Sprawdza, czy uwagi wyszukiwania z pustym napisem dają błąd walidacji, inaczej niż uwagi
    przy propozycji odpowiedzi, które mogą być puste.

    Wyłapuje puste uwagi przyjęte jako poprawne: także wtedy, gdy agent nic nie znalazł, ma
    napisać, czego szukał, bo przy pustej liście źródeł to jedyna informacja z wyszukiwania."""
    with pytest.raises(ValidationError):
        SearchNotes(internal_notes="")


def test_the_search_answer_takes_no_sources_from_the_model() -> None:
    """Sprawdza, czy odpowiedź wyszukiwania z dodatkowym polem, tu z listą źródeł, daje błąd
    walidacji.

    Wyłapuje źródła podane przez model obok uwag: lista źródeł ma powstawać z tego, co agent
    odczytał i zacytował, a nie z jego deklaracji."""
    with pytest.raises(ValidationError):
        SearchNotes.model_validate({"internal_notes": "Zgłoszenia: 41002.", "sources": ["41002"]})


def test_the_prompt_and_the_respond_tool_name_the_same_note_sections() -> None:
    """Sprawdza, czy wzór uwag w prompcie systemowym ma cztery sekcje z nagłówkiem `##`, o tych
    samych nazwach i w tej samej kolejności, w jakiej wymienia je opis narzędzia odpowiedzi:
    Zgłoszenia historyczne, Instrukcje i dokumentacja, Kod aplikacji, Nie znaleziono.

    Wyłapuje zmianę nagłówka w jednym z dwóch plików bez poprawienia drugiego: model dostałby
    dwa różne wzory uwag, a w diffie jednego pliku nie byłoby tego widać."""
    headings = [line for line in search.system_prompt().splitlines() if line.startswith("#")]
    tool     = " ".join(search.respond_tool().description.split())

    assert headings == [f"## {heading}" for heading in NOTE_HEADINGS]
    assert f"({', '.join(NOTE_HEADINGS)})" in tool
