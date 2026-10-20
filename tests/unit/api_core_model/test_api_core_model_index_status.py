import pytest
from pydantic import ValidationError

from app.core_model.instance.index_status import IndexStatus


@pytest.mark.parametrize(
    ("count", "state"),
    [(None, "missing"), (0, "empty"), (1, "built"), (171, "built")],
    ids=["brak", "zero", "jeden", "wiele"],
)
def test_the_state_follows_the_count(
    count: int | None,  # wstrzykiwane przez pytest z listy w dekoratorze wyżej
    state: str,         # oczekiwany stan dla tej liczby
) -> None:
    """Sprawdza, czy stan indeksu wynika z liczby jego elementów: bez liczby to brak indeksu
    („missing"), przy zerze indeks pusty („empty"), a przy jednym i większej liczbie indeks
    zbudowany („built").

    Wyłapuje pomylenie pustego indeksu z brakującym: brak kończy wywołania narzędzi błędem
    konfiguracji, a pusty indeks daje puste wyniki, więc belka frontu pokazałaby nie to, co się
    stanie przy pierwszym wyszukaniu."""
    status = IndexStatus(material="docs", index="sections", count=count)

    assert status.state == state


def test_the_state_goes_out_with_the_count() -> None:
    """Sprawdza, czy stan indeksu jest w zapisie modelu obok liczby, choć nikt go nie podaje.

    Wyłapuje stan, który istnieje tylko jako właściwość obiektu: mapowanie na odpowiedź trasy
    i test raportu czytają zapis modelu, więc stan by z niego zniknął."""
    status = IndexStatus(material="tickets", index="threads", count=0)

    assert status.model_dump() == {
        "material": "tickets",
        "index":    "threads",
        "count":    0,
        "state":    "empty",
    }


def test_a_negative_count_is_refused() -> None:
    """Sprawdza, czy liczba elementów mniejsza od zera kończy się błędem walidacji.

    Wyłapuje model, który przyjmuje liczbę bez sensu: ujemny licznik z bazy to usterka, którą
    stan „built" albo „empty" by ukrył."""
    with pytest.raises(ValidationError):
        IndexStatus(material="tickets", index="cards", count=-1)


def test_the_state_cannot_be_given_against_the_count() -> None:
    """Sprawdza, czy podanie stanu wprost, obok liczby, kończy się błędem walidacji.

    Wyłapuje model, w którym stan da się ustawić niezgodnie z liczbą („built" przy zerze):
    belka pokazywałaby zbudowany indeks, a narzędzia oddawałyby puste wyniki."""
    with pytest.raises(ValidationError):
        IndexStatus(material="tickets", index="cards", count=0, state="built")
