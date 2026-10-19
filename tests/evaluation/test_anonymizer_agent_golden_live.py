"""
Description:
Test ewaluacyjny silnika `agent` usługi `anonymizer` (p. 19.5) na golden secie anonimizatora:
ile danych przechodzi przez graf anonimizacji (wzorce, potem model wskazuje osoby i adresy)
i ile wiedzy niszczy, w zestawie zmyślonym i w próbce korpusu. Woła żywy model anonimizujący
z `.env` (`LLM_ANONYMIZATION_*`), więc chodzi tylko z `-m llm_live`.

| co mierzy                         | próg                                          |
|-----------------------------------|-----------------------------------------------|
| przecieki w zestawie zmyślonym    | `AGENT_MAX_LEAKS_SAFE`: 0 w każdym rodzaju    |
| przecieki w próbce korpusu        | `AGENT_MAX_LEAKS_UNSAFE`: 0 w każdym rodzaju  |
| zniszczona wiedza w obu zestawach | `AGENT_MAX_DESTROYED_*`: 0                    |

Co się dzieje po drodze:

1. `live_agent_settings()` bierze konfigurację modelu z `.env` i odmawia bez `-m llm_live`.
2. `measure_agent()` przepuszcza każdy tekst zestawu przez silnik `agent`, po kolei, i ocenia
   wynik słowami (`measure_anonymization()`).
3. Pomiar zestawu liczy się raz na plik testów (`remember_per_graph()`), a testy porównują jego
   liczniki z progami z `tests/_helpers/anonymizer_llm/`.

O czym pamiętać przy zmianach:

- Model nie jest deterministyczny przy temperaturze 0, więc próg to najgorszy wynik z kolejnych
  przebiegów, a czerwony test czyta się razem z przypadkami z komunikatu.
- Zmiana promptu węzła z modelem to ten pomiar, co najmniej dwa przebiegi.
- Przy próbce korpusu komunikat nazywa fragment rodzajem z numerem, nigdy treścią; `data/unsafe/`
  nie ma w repo, więc bez próbki jej przypadki się pomija.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from tests._helpers.anonymizer_llm import (
    AGENT_MAX_DESTROYED_SAFE,
    AGENT_MAX_DESTROYED_UNSAFE,
    AGENT_MAX_LEAKS_SAFE,
    AGENT_MAX_LEAKS_UNSAFE,
    leaks_over_threshold,
    live_agent_settings,
    measure_agent,
)
from tests._helpers.golden_anonymization import SAFE_FILE, UNSAFE_FILE, AnonymizationMeasurement
from tests._helpers.live import remember_per_graph
from tests._helpers.patterns import destroyed_fragments, leaked_fragments

pytestmark = pytest.mark.llm_live

# Oba zestawy z progami; próbka korpusu pomija się, gdy jej nie ma.
SETS = [
    pytest.param(SAFE_FILE, AGENT_MAX_LEAKS_SAFE, AGENT_MAX_DESTROYED_SAFE, id="safe"),
    pytest.param(
        UNSAFE_FILE,
        AGENT_MAX_LEAKS_UNSAFE,
        AGENT_MAX_DESTROYED_UNSAFE,
        id="unsafe",
        marks=pytest.mark.skipif(not UNSAFE_FILE.is_file(), reason="próbki korpusu nie ma w repo"),
    ),
]


@pytest.fixture(scope="module")
def measured(request: pytest.FixtureRequest) -> Callable[[str], AnonymizationMeasurement]:
    """
    Description:
    Pomiar silnika `agent` na zestawie, liczony raz na plik testów: oba testy zestawu dostają ten
    sam wynik, więc model nie jest wołany dwa razy za ten sam zestaw.

    Example args:
        request=<żądanie fixture pytest>

    Example result:
        funkcja: measured("data/safe/golden/anonymization.json") -> AnonymizationMeasurement(…)
    """
    settings = live_agent_settings(request.config)

    return remember_per_graph(lambda path: asyncio.run(measure_agent(Path(path), settings)))


@pytest.mark.parametrize(("path", "max_leaks", "max_destroyed"), SETS)
def test_agent_leaks_stay_within_the_threshold_of_each_kind(
    measured:      Callable[[str], AnonymizationMeasurement],
    path:          Path,
    max_leaks:     dict[str, int],
    max_destroyed: int,
) -> None:
    """Sprawdza, czy w każdym rodzaju danej — także imionach, nazwiskach i adresach bez kotwicy —
    przez silnik `agent` przechodzi najwyżej tyle fragmentów, ile mówi próg: zero w każdym rodzaju
    w obu zestawach.

    Wyłapuje prompt albo dopasowanie, po których zmianie model przestał wskazywać osobę
    w nagłówku maila, w odmianie czy w podpisie, albo kod przestał ją znajdować w tekście — zanim
    taka dana pójdzie do modelu zewnętrznego."""
    measurement = measured(str(path))
    over        = leaks_over_threshold(measurement, max_leaks)

    assert over == {}, f"przecieki ponad próg: {over}; {leaked_fragments(measurement, over)}"


@pytest.mark.parametrize(("path", "max_leaks", "max_destroyed"), SETS)
def test_agent_destroys_no_more_knowledge_than_the_threshold(
    measured:      Callable[[str], AnonymizationMeasurement],
    path:          Path,
    max_leaks:     dict[str, int],
    max_destroyed: int,
) -> None:
    """Sprawdza, czy silnik `agent` nie niszczy żadnej wiedzy z listy `keep` w obu zestawach:
    kodów i komunikatów błędów, wersji, nazw usług i aplikacji, słów podobnych do nazwisk.

    Wyłapuje model albo regułę odmian, po których zmianie znika nazwa aplikacji, kod błędu czy
    zwykłe słowo podobne do nazwiska („Lista” obok „Lis”, s33): nadgorliwość w korpusie jest
    nieodwracalna."""
    destroyed = destroyed_fragments(measured(str(path)))

    assert len(destroyed) <= max_destroyed, f"zniszczona wiedza ponad próg: {destroyed}"
