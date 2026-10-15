"""
Description:
Scenariusze ewaluacyjne rozwiązania na żywym modelu (p. 59): czy treść dla klienta w wariancie
`suggest_solution` niesie fakty z materiału — krok nieodwracalny z karty historycznej sprawy,
jego skutek i zastrzeżenie — i czy nie każe powtarzać kroku, który wątek pokazuje jako już
wykonany. Zestaw leży w `data/safe/golden/solution.json`; materiał to atrapy narzędzi (jeden
objaw, trzy przyczyny), a karty sprawy mogą mieć zmienione pola.

Każdy graf z sekcją w zestawie przechodzi przez dwa testy:

| test                                          | co sprawdza                                  |
|-----------------------------------------------|----------------------------------------------|
| `test_every_case_gets_an_accepted_answer`     | każda sprawa kończy się wynikiem             |
| `test_the_card_facts_reach_the_client_text`   | fakty z karty stoją w treści dla klienta     |

Pomiary:

| graf               | brak faktów z karty | pomiar                                         |
|--------------------|---------------------|------------------------------------------------|
| `suggest_solution` | 0 z 1               | 2026-10-15, `gpt-6.1-sol`, w dwóch przebiegach |

Licznik kroku już wykonanego (r01) pokazuje „jest” także wtedy, gdy model pisze, że kroku nie
proponuje, bo klient go wykonał — tak było w obu przebiegach; licznik słów nie odróżnia
proponowania od wspomnienia, więc czyta się treść.

O czym pamiętać przy zmianach:

- Progu nie ma: każdy brak to poprawka promptu. Sprawę poprawia się tylko wtedy, gdy błędna
  jest ona sama — na przykład wariant faktu nie obejmuje poprawnego brzmienia — nigdy pod wynik.
- Krok, który klient już wykonał, i nieodwracalność dopisana bez materiału to liczniki
  w raporcie, bez asercji; czy propozycja mimo to nie każe powtarzać kroku, czyta się w treści.
- KOSZTUJE: sprawa to pętla agenta z narzędziami, kilka tur modelu; cztery sprawy na
  `gpt-6.1-sol` to szacunkowo 0,1–0,15 USD i około minuty.
"""

import pytest

from tests._helpers.live import LiveUsageReport, live_generation_llm, remember_per_graph
from tests._helpers.scenarios.solution import (
    SolutionOutcomesOf,
    SolutionReport,
    measure_solution_cases,
    solution_sections,
)

pytestmark = pytest.mark.llm_live

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = solution_sections()


@pytest.fixture(scope="module")
def outcomes(
    request:         pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:      LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    solution_report: SolutionReport,         # wstrzykiwane przez pytest; raport ocen spraw
) -> SolutionOutcomesOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu przeprowadza jego sprawy na żywym modelu i oddaje ich
    oceny. Sprawy grafu liczą się przy pierwszym teście, który o nie poprosi, i są zapamiętane
    na cały plik — razem z błędem, jeśli przebieg się nim skończył.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: outcomes("suggest_solution") -> [SolutionOutcome(case=SolutionCase(…), …)]
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(
        lambda name: measure_solution_cases(name, llm, live_usage, solution_report)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_answer(graph: str, outcomes: SolutionOutcomesOf) -> None:
    """Sprawdza, czy każda sprawa kończy się na żywym modelu wynikiem, który węzeł odpowiedzi
    przyjął: propozycją albo samymi uwagami.

    Wyłapuje prompt, przy którym model nie umie oddać rozwiązania w kształcie narzędzia
    odpowiedzi nawet po poprawce: wdrożeniowiec dostaje wtedy błąd zamiast propozycji."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez wyniku — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_the_card_facts_reach_the_client_text(graph: str, outcomes: SolutionOutcomesOf) -> None:
    """Sprawdza, czy w każdej sprawie, której karta niesie krok nieodwracalny i zastrzeżenie,
    treść dla klienta niesie każdy z wymaganych faktów: sam krok, jego nieodwracalność
    i zastrzeżenie.

    Wyłapuje propozycję, która streszcza kartę i gubi ostrzeżenie: klient ponowi krok, którego
    skutków nie da się cofnąć, bo nikt mu nie napisał, że tak jest."""
    missing = [outcome for outcome in outcomes(graph) if outcome.missing]

    assert not missing, (
        f"{graph}: brak faktów z karty — "
        + "; ".join(f"{o.case.label}: {o.assessment}" for o in missing)
    )
