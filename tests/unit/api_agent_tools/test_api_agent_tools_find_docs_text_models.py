import pytest
from pydantic import ValidationError

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.docs.find_docs_text import FindDocsTextQuery
from app.agent_tools.docs.find_docs_text.models import MatchedSection


def test_a_query_with_nothing_to_search_is_refused() -> None:
    """Sprawdza, czy zapytanie bez frazy (`exact`) i bez słów (`words`) kończy się wyjątkiem
    `ValidationError`.

    Wyłapuje model, który przepuszcza puste zapytanie: wyszukiwanie oddałoby pustą listę, a ta
    wyglądałaby jak odpowiedź, że dokumentacja o tym milczy."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery()


@pytest.mark.parametrize(
    "arguments",
    [{"exact": "Uprawnienia → Kancelaria"}, {"words": "uprawnienie kancelaria"}],
    ids=["exact", "words"],
)
def test_one_field_is_enough(arguments: dict) -> None:
    """Sprawdza, czy zapytanie z samą frazą (`exact`) albo z samymi słowami (`words`) jest poprawne;
    każdy z tych dwóch przypadków jest sprawdzany osobno.

    Wyłapuje walidację, która wymaga obu pól naraz: agent, który ma tylko nazwę opcji albo tylko
    słowa kluczowe, nie mógłby wtedy szukać."""
    assert FindDocsTextQuery(**arguments)


def test_a_too_short_exact_text_is_refused() -> None:
    """Sprawdza, czy fraza krótsza niż trzy znaki (tu „50”) kończy się wyjątkiem `ValidationError`.

    Wyłapuje brak dolnej granicy długości frazy: tak krótki ciąg trafiałby w przypadkowe miejsca
    dokumentacji."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(exact="50")


def test_a_phrase_is_measured_and_kept_without_the_spaces_around_it() -> None:
    """Sprawdza, czy spacje wokół frazy się nie liczą: fraza z samych spacji kończy się wyjątkiem
    `ValidationError`, a „EDR-0417” podane ze spacjami po obu stronach zostaje zapisane bez nich.

    Wyłapuje dwie usterki: frazę z samych spacji, która pasowałaby do każdego tekstu, oraz spacje na
    brzegach frazy, które rozstrzygałyby o tym, czy sekcja zostanie znaleziona."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(exact="   ")

    assert FindDocsTextQuery(exact="  EDR-0417 ").exact == "EDR-0417"


def test_exact_takes_one_phrase_not_a_list() -> None:
    """Sprawdza, czy lista dwóch fraz podana w polu `exact` kończy się wyjątkiem `ValidationError`.

    Wyłapuje powrót do kilku fraz w jednym wywołaniu: wynik nie mówiłby wtedy, która z nich
    trafiła."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(exact=["EDR-0417", "Przekaż bufor"])


def test_an_unknown_argument_is_refused() -> None:
    """Sprawdza, czy argument spoza schematu (tu `limit=20`) kończy się wyjątkiem `ValidationError`.

    Wyłapuje model, który po cichu ignoruje nieznane argumenty: agent myślałby, że sam ustawił
    liczbę trafień, a o niej decyduje konfiguracja."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(words="uprawnienie", limit=20)


def test_a_matched_section_carries_no_snippet() -> None:
    """Sprawdza, czy znalezionej sekcji nie da się zbudować z dodatkowym polem na fragment treści
    (`snippet`): taka próba kończy się wyjątkiem `ValidationError`.

    Wyłapuje fragment treści dołożony do wyniku wyszukiwania: treść ma dawać wyłącznie odczyt
    sekcji, bo tylko on trafia na listę źródeł."""
    with pytest.raises(ValidationError):
        MatchedSection(matched_by="exact", section=default_sections()[0], snippet="Uprawnienie…")
