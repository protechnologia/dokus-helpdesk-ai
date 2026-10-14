"""
Description:
Scenariusze ewaluacyjne „Popraw” na żywym modelu (p. 59): czy poprawiony tekst zmienia formę
notatek wdrożeniowca, a nie ich treść — słowa potoczne znikają, fakty zostają, nie przybywa
liczb ani nazw. Zestaw leży w `data/safe/golden/polish.json`; każda sprawa to notatki z listą
słów potocznych, faktów i pułapek, czyli dopisków, które kuszą model.

Każdy graf z sekcją w zestawie przechodzi przez cztery testy:

| test                                     | co sprawdza                                        |
|------------------------------------------|----------------------------------------------------|
| `test_every_case_gets_an_accepted_text`  | każda sprawa kończy się tekstem                    |
| `test_colloquial_words_disappear`        | żadne słowo potoczne z notatek nie zostaje         |
| `test_facts_from_the_notes_stay`         | żaden fakt z notatek nie ginie                     |
| `test_no_numbers_or_names_are_added`     | nie przybywa liczb ani dopisków z pułapek          |

Pomiary:

| graf     | potoczne | zgubione | dopisane | pomiar                                         |
|----------|----------|----------|----------|------------------------------------------------|
| `polish` | 0 z 4    | 0 z 4    | 0 z 4    | 2026-10-14, `gpt-6.1-sol`, w dwóch przebiegach |

O czym pamiętać przy zmianach:

- Progu nie ma: każde słowo potoczne, zgubiony fakt i dopisek to poprawka promptu. Sprawę
  poprawia się tylko wtedy, gdy błędna jest ona sama, nigdy pod wynik.
- Listy łapią tylko to, co przewidział autor sprawy: krok albo obietnica spoza pułapek wyjdzie
  wyłącznie w poprawionym tekście, który raport wypisuje w całości. Czyta się go przy pierwszym
  pomiarze i przy każdej zmianie wyniku.
- Zasady stylu bierze się z zestawu domyślnego, tak jak trasa. Sekcja zapisuje wersję zestawu,
  pod którą ją napisano; przy innej wersji test kończy się błędem, zanim zawoła model.
- KOSZTUJE: sprawa to jedna tura modelu, a `polish` ma cztery sprawy: na `gpt-6.1-sol`
  0,01 USD i kilka sekund.
"""

import asyncio
import importlib
from collections.abc import Callable

import pytest

from app.agent_nodes.respond import MAX_RETRIES
from app.config import LLMSettings
from tests.conftest import live_generation_llm
from tests.helpers_live_graphs import default_rules, remember_per_graph, run_live_cases
from tests.helpers_live_usage import LiveUsageReport
from tests.helpers_polish import PolishOutcome, PolishReport, judge_polish_case, polish_sections

pytestmark = pytest.mark.llm_live

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = polish_sections()

# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
OutcomesOf = Callable[[str], list[PolishOutcome]]


@pytest.fixture(scope="module")
def outcomes(
    request:       pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:    LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    polish_report: PolishReport,           # wstrzykiwane przez pytest; raport ocen spraw
) -> OutcomesOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu przeprowadza jego sprawy na żywym modelu i oddaje ich
    oceny. Sprawy grafu liczą się przy pierwszym teście, który o nie poprosi, i są zapamiętane
    na cały plik — razem z błędem, jeśli przebieg się nim skończył.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: outcomes("polish") -> [PolishOutcome(case=PolishCase(case_id="s01", …), …), …]
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(lambda name: _measure(name, llm, live_usage, polish_report))


def _measure(
    name:          str,              # np. "polish"
    llm:           LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:    LiveUsageReport,  # raport zużycia przebiegu
    polish_report: PolishReport,     # raport ocen spraw
) -> list[PolishOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy grafu na żywym modelu, z zasadami stylu z zestawu domyślnego,
    ocenia je, zgłasza do obu raportów i oddaje oceny. Sekcja pod inną wersją zasad kończy
    pomiar, zanim zawoła model.

    Example args:
        name="polish"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        polish_report=PolishReport()

    Example result:
        [PolishOutcome(case=PolishCase(case_id="s01", …), colloquial=(), lost=(), …), …]

    Raises:
        AssertionError: zasady stylu w innej wersji niż sekcja
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = SECTIONS[name]
    graph   = importlib.import_module(f"app.agent_graphs.{name}")
    rules   = default_rules(name, section.rules_version)

    finals = asyncio.run(run_live_cases(graph, llm, [(case.text, rules) for case in section.cases]))

    judged: list[PolishOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"popraw {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_polish_case(
            case    = case,
            output  = None if final is None else final.output,
            retries = MAX_RETRIES if final is None else final.respond_retries,
        )

        polish_report.record(name, outcome)
        judged.append(outcome)

    return judged


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_text(graph: str, outcomes: OutcomesOf) -> None:
    """Sprawdza, czy każda sprawa „Popraw” kończy się na żywym modelu tekstem, który węzeł
    odpowiedzi przyjął.

    Wyłapuje prompt, przy którym model nie umie oddać tekstu narzędziem odpowiedzi nawet po
    poprawce: wdrożeniowiec dostaje wtedy błąd zamiast poprawionej wiadomości."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez tekstu — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_colloquial_words_disappear(graph: str, outcomes: OutcomesOf) -> None:
    """Sprawdza, czy w żadnym poprawionym tekście nie zostaje słowo potoczne z notatek.

    Wyłapuje „Popraw”, które przepisuje notatki prawie dosłownie: wiadomość z „śmiga” albo
    „sorki” wychodzi do klienta, choć zasady stylu każą pisać bez potocznego słownictwa."""
    left = [outcome for outcome in outcomes(graph) if outcome.colloquial]

    assert not left, (
        f"{graph}: słowa potoczne zostały — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in left)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_facts_from_the_notes_stay(graph: str, outcomes: OutcomesOf) -> None:
    """Sprawdza, czy każdy fakt z notatek (liczba, skrót, nazwa produktu) zostaje w poprawionym
    tekście.

    Wyłapuje „Popraw”, które wygładza notatki kosztem treści: gubi limit, liczbę przesyłek albo
    nazwę usługi, a klient dostaje uprzejmą wiadomość bez tego, co miał wiedzieć."""
    lost = [outcome for outcome in outcomes(graph) if outcome.lost]

    assert not lost, (
        f"{graph}: zgubione fakty — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in lost)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_no_numbers_or_names_are_added(graph: str, outcomes: OutcomesOf) -> None:
    """Sprawdza, czy w żadnym poprawionym tekście nie ma liczby spoza notatek ani dopisku
    z pułapek sprawy (ścieżki menu, terminu, dodatkowego kroku).

    Wyłapuje „Popraw”, które dodaje fakt: termin poprawki, wersję, miejsce w menu albo krok,
    którego wdrożeniowiec nie napisał — to jedyna funkcja, której tekst idzie do klienta, więc
    dodany fakt trafia prosto do niego (zasada 9)."""
    added = [outcome for outcome in outcomes(graph) if outcome.new_numbers or outcome.added]

    assert not added, (
        f"{graph}: dopisane fakty — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in added)
    )
