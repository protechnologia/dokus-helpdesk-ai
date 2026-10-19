"""
Description:
Test ewaluacyjny wzorców usługi `anonymizer` (p. 19.4) na golden secie anonimizatora: ile danych
o stałym kształcie przechodzi przez zamianę wzorcami i ile wiedzy zamiana niszczy, w zestawie
zmyślonym i w próbce korpusu. Imion i nazwisk wzorce nie łapią (p. 19.5), więc ich przecieków
test nie liczy.

| co mierzy                         | próg                                | zmierzone dziś |
|-----------------------------------|-------------------------------------|----------------|
| przecieki w zestawie zmyślonym    | `MAX_LEAKS_SAFE`: adresy 14, inne 0 | jak próg       |
| przecieki w próbce korpusu        | `MAX_LEAKS_UNSAFE`: 0 w każdym      | jak próg       |
| zniszczona wiedza w obu zestawach | 0                                   | 0              |

Po co: wzorzec bez sumy kontrolnej (telefon, adres) łatwo poszerzyć tak, że zacznie zjadać kody
błędów, wersje i numery spraw, a zwężyć tak, że przepuści zapis, który w korpusie stoi. Testy
jednostkowe wzorców pilnują przykładów, ten test — całych wątków.

Co się dzieje po drodze:

1. `measure_anonymization()` z `tests/_helpers/golden_anonymization/` przepuszcza każdy tekst
   zestawu przez `replace_patterns()` i ocenia wynik słowami.
2. Liczy przecieki na rodzaj danej i zniszczoną wiedzę na rodzaj wiedzy.
3. Test porównuje liczniki rodzajów od wzorców z progami z `tests/_helpers/patterns/`.

O czym pamiętać przy zmianach:

- Wzorce są deterministyczne, więc próg to zmierzona liczba: nowy przeciek albo zniszczona
  wiedza daje czerwony test, a poprawa wzorca każe obniżyć próg.
- Adresy zestawu zmyślonego bez kotwicy, małymi literami i złamane na linie (14) to znane braki
  wzorców: wskazuje je model (p. 19.5).
- Przy próbce korpusu komunikat nazywa fragment rodzajem z numerem, nigdy treścią.
- `data/unsafe/` nie ma w repo (PII), więc bez próbki korpusu jej przypadki się pomija.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

from tests._helpers.golden_anonymization import (
    SAFE_FILE,
    UNSAFE_FILE,
    AnonymizationMeasurement,
    anonymization_set,
    measure_anonymization,
)
from tests._helpers.patterns import (
    MAX_LEAKS_SAFE,
    MAX_LEAKS_UNSAFE,
    PATTERN_KINDS,
    anonymize_with_patterns,
    destroyed_fragments,
    kinds_over_threshold,
    leaked_fragments,
    removed_kinds,
)

# Oba zestawy z progami przecieków; próbka korpusu pomija się, gdy jej nie ma.
SETS = [
    pytest.param(SAFE_FILE, MAX_LEAKS_SAFE, id="safe"),
    pytest.param(
        UNSAFE_FILE,
        MAX_LEAKS_UNSAFE,
        id="unsafe",
        marks=pytest.mark.skipif(not UNSAFE_FILE.is_file(), reason="próbki korpusu nie ma w repo"),
    ),
]


@pytest.fixture
async def measurement(request: pytest.FixtureRequest) -> AnonymizationMeasurement:
    """
    Description:
    Mierzy zamianę wzorcami na zestawie z parametru testu. Cały zestaw liczy się w ułamku
    sekundy, więc pomiar nie jest dzielony między testy.

    Example args:
        request=<parametr testu: ścieżka zestawu>

    Example result:
        AnonymizationMeasurement(outcomes=(…), leaks={"PESEL": KindCount(found=0, total=3), …}, …)
    """
    golden = anonymization_set(request.param)

    return await measure_anonymization(golden, anonymize_with_patterns)


@pytest.mark.parametrize(("measurement", "max_leaks"), SETS, indirect=["measurement"])
def test_pattern_leaks_stay_within_the_threshold_of_each_kind(
    measurement: AnonymizationMeasurement,
    max_leaks:   Mapping[str, int],
) -> None:
    """Sprawdza, czy w każdym rodzaju danej o stałym kształcie przez zamianę wzorcami przechodzi
    najwyżej tyle fragmentów, ile mówi próg zestawu: w zestawie zmyślonym 14 adresów i zero
    pozostałych, w próbce korpusu zero w każdym rodzaju, który w niej stoi.

    Wyłapuje wzorzec, który po zmianie przestał łapać zapis stojący w zestawie (numer z twardą
    spacją, kierunkowy w nawiasie, adres z „lok.”), zanim taka dana pójdzie do modelu
    zewnętrznego."""
    over = kinds_over_threshold(measurement, max_leaks)

    assert over == {}, f"przecieki ponad próg: {over}; {leaked_fragments(measurement, over)}"


@pytest.mark.parametrize(("measurement", "max_leaks"), SETS, indirect=["measurement"])
def test_patterns_destroy_no_knowledge(
    measurement: AnonymizationMeasurement,
    max_leaks:   Mapping[str, int],
) -> None:
    """Sprawdza, czy zamiana wzorcami nie niszczy w zestawie żadnej wiedzy z listy `keep`:
    kodów i komunikatów błędów, wersji, nazw usług, numerów spraw i słów, które tylko wyglądają
    na daną.

    Wyłapuje wzorzec poszerzony tak, że zamienia na znacznik numer przesyłki, kod błędu albo
    sygnaturę sprawy: nadgorliwość w korpusie jest nieodwracalna, bo z takiego wątku nikt już nie
    odczyta, czego sprawa dotyczyła."""
    assert destroyed_fragments(measurement) == []


@pytest.mark.parametrize(("path", "max_leaks"), SETS)
def test_every_pattern_kind_of_a_set_has_a_threshold(
    path:      Path,
    max_leaks: Mapping[str, int],
) -> None:
    """Sprawdza, czy każdy rodzaj od wzorców, który stoi w zestawie, ma próg tego zestawu.

    Wyłapuje nowy wzorzec bez progu: pomiar liczyłby go z progiem zero, którego nie widać
    w stałych helpera."""
    assert removed_kinds(path) & set(PATTERN_KINDS) <= set(max_leaks)


def test_the_synthetic_set_has_every_pattern_kind() -> None:
    """Sprawdza, czy zestaw zmyślony ma choć jeden fragment każdego rodzaju od wzorców.

    Wyłapuje rodzaj, którego żaden przypadek nie sprawdza: w próbce korpusu nie ma dziś konta,
    dowodu, paszportu ani adresu do e-Doręczeń, więc tylko zestaw zmyślony pokazałby ich
    przeciek."""
    assert set(PATTERN_KINDS) <= removed_kinds(SAFE_FILE)
