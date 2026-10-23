"""
Description:
Scenariusze ewaluacyjne „pytań już nie trzeba” na żywym modelu (p. 59): czy wariant
`suggest_questions` oddaje pytania wtedy, gdy fakty ze zgłoszenia zostawiają konkurujące
przyczyny, a `text: null` z uwagami wtedy, gdy fakty — z opisu albo z odpowiedzi klienta
w wątku — rozstrzygają sprawę. Zestaw leży w `data/safe/golden/questions.json`; przyczyny
pochodzą z materiału atrap narzędzi (jeden objaw, trzy rozłączne przyczyny).

Każdy graf z sekcją w zestawie przechodzi przez trzy testy:

| test                                          | co sprawdza                                   |
|-----------------------------------------------|-----------------------------------------------|
| `test_every_case_gets_an_accepted_answer`     | każda sprawa kończy się wynikiem              |
| `test_no_questions_once_the_facts_settle_it`  | przy sprawie rozstrzygniętej pytań nie ma     |
| `test_questions_while_causes_compete`         | przy konkurujących przyczynach pytania są     |

Pomiary:

| graf                | pytania zbędne | brak pytań | pomiar                                     |
|---------------------|----------------|------------|--------------------------------------------|
| `suggest_questions` | 0 z 2          | 0 z 2      | 2026-10-15, `gpt-6.1-sol`, trzy przebiegi  |

O czym pamiętać przy zmianach:

- Progu nie ma: każdy błędny wybór to poprawka promptu. Sprawę poprawia się tylko wtedy, gdy
  błędna jest ona sama, nigdy pod wynik.
- Sprawa rozstrzygnięta niesie fakt, który wskazuje jedną przyczynę wprost, a nie tylko
  zawęża; inaczej brak pytań nie byłby jedyną dobrą odpowiedzią.
- Liczy się, czy pytania są. Czy uwagi nazywają fakty, które wykluczyły przyczyny, i czy pytania
  nie powtarzają tych, na które klient odpowiedział, czyta się w raporcie.
- KOSZTUJE: sprawa to pętla agenta z narzędziami, kilka tur modelu; cztery sprawy na
  `gpt-6.1-sol` to 0,09 USD i około minuty.
"""


import pytest

from tests._helpers.live import (
    LiveUsageReport,
    live_generation_llm,
    remember_per_graph,
)
from tests._helpers.scenarios.questions import (
    QuestionsOutcomesOf,
    QuestionsReport,
    measure_questions_cases,
    questions_sections,
)

pytestmark = pytest.mark.llm_live

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = questions_sections()


@pytest.fixture(scope="module")
def outcomes(
    request:          pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:       LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    questions_report: QuestionsReport,        # wstrzykiwane przez pytest; raport ocen spraw
) -> QuestionsOutcomesOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu przeprowadza jego sprawy na żywym modelu i oddaje ich
    oceny. Sprawy grafu liczą się przy pierwszym teście, który o nie poprosi, i są zapamiętane
    na cały plik — razem z błędem, jeśli przebieg się nim skończył.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: outcomes("suggest_questions") -> [QuestionsOutcome(case=QuestionsCase(…), …)]
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(
        lambda name: measure_questions_cases(name, llm, live_usage, questions_report)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_answer(graph: str, outcomes: QuestionsOutcomesOf) -> None:
    """Sprawdza, czy każda sprawa kończy się na żywym modelu wynikiem, który węzeł odpowiedzi
    przyjął: pytaniami albo samymi uwagami.

    Wyłapuje prompt, przy którym model nie umie oddać odpowiedzi w kształcie narzędzia
    odpowiedzi nawet po poprawce, na przykład oddaje `text: null` bez uwag: wdrożeniowiec
    dostaje wtedy błąd zamiast pytań."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez wyniku — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_no_questions_once_the_facts_settle_it(graph: str, outcomes: QuestionsOutcomesOf) -> None:
    """Sprawdza, czy przy każdej sprawie, której fakty — z opisu albo z odpowiedzi klienta
    w wątku — zostawiają jedną przyczynę, wariant oddaje brak pytań zamiast listy.

    Wyłapuje prompt, który pyta na siłę: klient dostaje pytania o rzeczy, które już opisał,
    a wdrożeniowiec — odpowiedź gorszą niż wskazanie, co sprawdzić po naszej stronie."""
    needless = [outcome for outcome in outcomes(graph) if outcome.needless]

    assert not needless, (
        f"{graph}: pytania przy sprawie rozstrzygniętej — "
        + ", ".join(outcome.case.label for outcome in needless)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_questions_while_causes_compete(graph: str, outcomes: QuestionsOutcomesOf) -> None:
    """Sprawdza, czy przy każdej sprawie, której fakty nie rozróżniają konkurujących przyczyn,
    wariant oddaje pytania, a nie „pytań już nie trzeba”.

    Wyłapuje fałszywe wyjście bez pytań przy zgodnym objawie i różnych przyczynach — najgroźniejszy
    błąd tego wariantu: wdrożeniowiec zostaje z jedną hipotezą, a pozostałych nikt nie sprawdzi."""
    missing = [outcome for outcome in outcomes(graph) if outcome.missing]

    assert not missing, (
        f"{graph}: brak pytań przy konkurujących przyczynach — "
        + ", ".join(outcome.case.label for outcome in missing)
    )
