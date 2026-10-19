"""
Description:
Spójność golden setu anonimizatora bez silnika: zestaw zmyślony
(`data/safe/golden/anonymization.json`) i próbka korpusu (`data/unsafe/golden/anonymization.json`).
Zaznaczenia pisze się ręcznie, a pomyłka w nich nie daje błędu, tylko fałszywy wynik pomiaru,
więc te warunki pilnuje się w domyślnym `pytest`, zanim zestaw zmierzy wzorce (p. 19.4)
i silnik (p. 19.5).

| warunek                                          | czym grozi jego brak                      |
|--------------------------------------------------|-------------------------------------------|
| metryczka mówi, czy zestaw jest zmyślony         | fragmenty z danymi klienta w konsoli      |
| przypadki mają różne identyfikatory              | wynik, w którym nie wiadomo, o który      |
|                                                  | przypadek chodzi                          |
| zaznaczenia pasują do tekstu                     | dana, która nigdy nie wycieknie, albo     |
|                                                  | wiedza, której nie da się zniszczyć       |
| zestaw zmyślony ma każdy rodzaj danej i wiedzy   | rodzaj, którego żaden pomiar nie widzi    |
| wzorcowa zamiana wychodzi bez błędu              | zestaw, którego nie przejdzie nawet       |
|                                                  | idealny silnik                            |
| atrapa silnika przepuszcza każdą daną            | ocena ślepa na przeciek                   |

Bez próbki korpusu (dane klientów, poza repo) jej parametry się pomija, a nie padają, jak
w testach ewaluacyjnych na korpusie.
"""

from pathlib import Path

import pytest

from anonymizer_app.core_engine import FakeEngine
from tests._helpers.golden_anonymization import (
    KEEP_KINDS,
    REMOVE_KINDS,
    SAFE_FILE,
    UNSAFE_FILE,
    AnonymizationCase,
    annotation_problems,
    anonymization_set,
    ideal_anonymizer,
    measure_anonymization,
)

# Oba zestawy jako parametry: próbka korpusu pomija się, gdy jej nie ma.
SETS = [
    pytest.param(SAFE_FILE, True, id="safe"),
    pytest.param(
        UNSAFE_FILE,
        False,
        id="unsafe",
        marks=pytest.mark.skipif(not UNSAFE_FILE.is_file(), reason="próbki korpusu nie ma w repo"),
    ),
]

# Przypadki obu zestawów, czytane przy imporcie: z nich powstają parametry testu zaznaczeń.
CASES = [
    case
    for path in (SAFE_FILE, UNSAFE_FILE)
    if path.is_file()
    for case in anonymization_set(path).cases
]


@pytest.mark.parametrize(("path", "synthetic"), SETS)
def test_a_set_says_whether_it_is_synthetic_and_has_unique_ids(path: Path, synthetic: bool) -> None:
    """Sprawdza, czy metryczka zestawu zmyślonego mówi, że jest zmyślony, a próbki korpusu, że
    nie jest, i czy identyfikatory przypadków się nie powtarzają.

    Wyłapuje próbkę korpusu oznaczoną jako zmyśloną — ocena i komunikaty pokazywałyby wtedy dane
    klientów w konsoli — i dwa przypadki o jednym identyfikatorze w wynikach pomiaru."""
    golden = anonymization_set(path)
    ids    = [case.case_id for case in golden.cases]

    assert golden.synthetic is synthetic
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_every_case_is_marked_consistently(case: AnonymizationCase) -> None:
    """Sprawdza, czy zaznaczenia przypadku pasują do jego tekstu: rodzaje są z listy, każdy
    fragment stoi w tekście, dana nie stoi tylko wewnątrz innej, dane nie zachodzą na siebie
    częściowo, a wiedza nie zachodzi na daną.

    Wyłapuje literówkę w zaznaczeniu i fragment bez skutku: taka dana nigdy by nie wyciekła,
    a wiedza nigdy nie zginęła, więc pomiar silnika wyglądałby lepiej, niż jest."""
    assert annotation_problems(case) == ()


def test_the_synthetic_set_covers_every_kind() -> None:
    """Sprawdza, czy zestaw zmyślony ma choć jeden fragment każdego rodzaju danej i wiedzy.

    Wyłapuje rodzaj, którego zestaw nie sprawdza: przy próbce korpusu bez tego rodzaju (dziś
    nie ma w niej numeru konta ani dowodu) żaden pomiar nie pokazałby, że silnik go przepuszcza."""
    golden  = anonymization_set(SAFE_FILE)
    removed = {fragment.kind for case in golden.cases for fragment in case.remove}
    kept    = {fragment.kind for case in golden.cases for fragment in case.keep}

    assert removed == set(REMOVE_KINDS)
    assert kept    == set(KEEP_KINDS)


@pytest.mark.parametrize(("path", "synthetic"), SETS)
async def test_the_marked_replacement_leaves_no_leak_and_destroys_nothing(
    path:      Path,
    synthetic: bool,
) -> None:
    """Sprawdza, czy zamiana dokładnie zaznaczonych danych na znaczniki wychodzi w pomiarze bez
    żadnego przecieku i bez zniszczonej wiedzy, w każdym przypadku zestawu.

    Wyłapuje zestaw, którego nie przejdzie nawet idealny silnik: słowo danej, które stoi w tekście
    także poza zaznaczeniem, albo wiedzę, którą zamiana danej musi naruszyć."""
    golden      = anonymization_set(path)
    measurement = await measure_anonymization(golden, ideal_anonymizer(golden))

    assert [outcome.case.case_id for outcome in measurement.outcomes
            if outcome.assessment != "zgodny"] == []


@pytest.mark.parametrize(("path", "synthetic"), SETS)
async def test_the_fake_engine_leaks_every_marked_fragment(path: Path, synthetic: bool) -> None:
    """Sprawdza, czy atrapa silnika usługi, która oddaje tekst bez zmian, ma w pomiarze przeciek
    każdej zaznaczonej danej w każdym rodzaju i nie niszczy żadnej wiedzy.

    Wyłapuje pomiar, który nie widzi przecieku, i przypadek, w którym ocena liczyłaby zniszczoną
    wiedzę bez żadnej zmiany tekstu: oba dałyby fałszywe liczby przy pierwszym silniku."""
    measurement = await measure_anonymization(anonymization_set(path), FakeEngine().anonymize)

    assert all(count.found == count.total for count in measurement.leaks.values())
    assert all(count.found == 0 for count in measurement.destroyed.values())
