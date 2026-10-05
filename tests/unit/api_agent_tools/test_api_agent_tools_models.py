from datetime import date

import pytest
from pydantic import ValidationError

from app.agent_tools import SourceRef


def make_ref(
    source:  str = "tickets",                                # e.g. "docs"
    item_id: str = "33644",                                  # e.g. "doc-7"
    title:   str = "Wysyłka przez ePUAP kończy się błędem",  # e.g. "Instrukcja administratora 4.12"
) -> SourceRef:
    """
    Description:
    Builds a valid source reference, so each test changes only the one field it is about.

    Example args:
        source="tickets"
        item_id="33644"
        title="Wysyłka przez ePUAP kończy się błędem"

    Example result:
        SourceRef(source="tickets", item_id="33644", title="Wysyłka…", date=date(2026, 3, 14))
    """
    return SourceRef(
        source  = source,
        item_id = item_id,
        title   = title,
        date    = date(2026, 3, 14),
    )


def test_key_tells_sources_apart() -> None:
    """Sprawdza, czy klucz źródła składa się z materiału i identyfikatora (`tickets:33644`), więc
    ten sam identyfikator w zgłoszeniach i w dokumentacji daje dwa różne klucze.

    Wyłapuje klucz zbudowany z samego identyfikatora: usuwanie powtórzeń ze źródeł jednej odpowiedzi
    scaliłoby wtedy zgłoszenie z fragmentem dokumentacji."""
    ticket   = make_ref(source="tickets", item_id="33644")
    fragment = make_ref(source="docs",    item_id="33644")

    assert ticket.key   == "tickets:33644"
    assert ticket.key   != fragment.key


def test_a_ref_carries_no_score() -> None:
    """Sprawdza, czy wpis źródła z polem `score` kończy się `ValidationError`.

    Wyłapuje powrót podobieństwa na listę źródeł: źródłem jest to, co model odczytał po
    identyfikatorze, a odczyt podobieństwa nie zna. Podobieństwo pokazuje modelowi wyszukiwanie,
    czytelnik odpowiedzi go nie dostaje."""
    with pytest.raises(ValidationError):
        SourceRef(source="docs", item_id="doc-7", title="Instrukcja administratora", score=0.87)


def test_a_ref_may_have_no_date() -> None:
    """Sprawdza, czy wpis źródła bez daty jest przyjmowany, a jego data to `None`.

    Wyłapuje datę zamienioną w pole wymagane: sekcja dokumentacji może pochodzić z wydania bez
    podanej daty i nie dałoby się jej wtedy zacytować."""
    ref = SourceRef(source="docs", item_id="doc-7", title="Instrukcja administratora 4.12")

    assert ref.date is None


@pytest.mark.parametrize("field", ["source", "item_id", "title"])
def test_empty_identity_is_refused(field: str) -> None:
    """Sprawdza, czy wpis źródła z pustym materiałem, pustym identyfikatorem albo pustym tytułem
    kończy się `ValidationError`.

    Wyłapuje wpis, którego nie da się wskazać albo rozpoznać: źródła, którego nikt nie
    zidentyfikuje, nie można zacytować, a takiego, którego nikt nie rozpozna, nie można
    sprawdzić."""
    with pytest.raises(ValidationError):
        make_ref(**{field: ""})


def test_an_unknown_field_is_refused() -> None:
    """Sprawdza, czy wpis źródła z polem spoza kontraktu (tu `rank`) kończy się `ValidationError`.

    Wyłapuje wpis, który po cichu przyjmuje albo gubi nieznane pola: rozjazd z kontraktem ma wyjść
    jako błąd, tak samo jak w karcie zgłoszenia, a nie zostać wchłonięty jako rozszerzenie."""
    with pytest.raises(ValidationError):
        SourceRef(source="tickets", item_id="33644", title="x", rank=1)
