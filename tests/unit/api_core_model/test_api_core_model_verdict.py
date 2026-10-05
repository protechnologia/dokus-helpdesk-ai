import pytest
from pydantic import ValidationError

from app.core_model.graphs.verdict import Verdict


def test_a_pass_needs_no_explanation() -> None:
    """Sprawdza, czy werdykt przepuszczający (`pass`) bez uzasadnienia i bez wskazówki jest
    poprawny, a lista uzasadnień jest wtedy pusta.

    Wyłapuje walidację, która żąda uzasadnienia także przy przepuszczeniu: każdy werdykt `pass`
    byłby odrzucany, choć przepuszczenie nie wymaga tłumaczenia."""
    assert Verdict(verdict="pass").reasons == []


@pytest.mark.parametrize(
    "fields",
    [
        {"hint": "Dopisz, co zmieniono."},
        {"reasons": ["Nie widać zmian."]},
        {"reasons": ["Nie widać zmian."], "hint": "   "},
    ],
    ids=["no-reasons", "no-hint", "blank-hint"],
)
def test_a_block_without_reasons_or_hint_is_rejected(fields: dict[str, object]) -> None:
    """Sprawdza, czy werdykt blokujący (`block`) bez uzasadnienia, bez wskazówki albo ze
    wskazówką z samych spacji daje błąd walidacji.

    Wyłapuje blokadę bez wyjaśnienia, czyli złamanie zasady 10: samo „nie", bez powodu i bez
    podpowiedzi, co dopisać, zamienia bramkę jakości w przeszkodę, którą ludzie nauczą się
    obchodzić na ślepo."""
    with pytest.raises(ValidationError):
        Verdict(verdict="block", **fields)


def test_a_block_with_reasons_and_hint_is_accepted() -> None:
    """Sprawdza, czy werdykt blokujący z uzasadnieniem i wskazówką jest poprawny także wtedy, gdy
    lista braków (`missing`) nie została podana — jest wtedy pusta.

    Wyłapuje walidację, która wymaga też listy braków: poprawnie uzasadniona blokada byłaby
    odrzucana jak błąd formatu odpowiedzi modelu."""
    verdict = Verdict(verdict="block", reasons=["Nie widać zmian."], hint="Dopisz, co zmieniono.")

    assert verdict.missing == []


def test_an_unknown_key_is_an_error() -> None:
    """Sprawdza, czy klucz, którego werdykt nie przewiduje (tu `confidence` w odpowiedzi modelu),
    daje błąd walidacji.

    Wyłapuje ciche odrzucanie pól dołożonych przez model: odpowiedź w innym kształcie niż
    umówiony przeszłaby jako poprawna, a dołożona treść zniknęłaby bez śladu."""
    with pytest.raises(ValidationError):
        Verdict.model_validate({"verdict": "pass", "confidence": 0.9})
