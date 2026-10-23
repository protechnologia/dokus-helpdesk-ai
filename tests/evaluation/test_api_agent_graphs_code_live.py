"""
Description:
Scenariusze ewaluacyjne cytowania kodu na żywym modelu (p. 59): czy graf z narzędziami kodu
cytuje jako przyczynę plik, w którym stoi komunikat ze zgłoszenia, czy nie cytuje przyczyny, gdy
komunikatu nie ma w kodzie nigdzie, choć podobny kusi, i czy cytuje tylko linie, które wcześniej
przeczytał. Zestaw leży w `data/safe/golden/code.json`: jedna lista spraw, a każda wymienia
w `graphs` grafy, na których idzie (`search`, `suggest_questions`, `suggest_solution`);
narzędzia kodu są prawdziwe, na paczce aplikacji syntetycznej, a zgłoszenia i instrukcje to
atrapy.

Każdy graf, który sprawy wymieniają w `graphs`, przechodzi przez cztery testy:

| test                                                  | co sprawdza                           |
|-------------------------------------------------------|---------------------------------------|
| `test_every_case_gets_an_accepted_answer`             | każda sprawa kończy się wynikiem      |
| `test_the_file_with_the_message_is_quoted_as_cause`   | plik z komunikatem wśród przyczyn     |
| `test_no_cause_is_quoted_when_the_message_is_nowhere` | bez komunikatu w kodzie bez przyczyny |
| `test_every_quote_points_at_lines_read_before`        | cytowane linie były wcześniej czytane |

Pomiary:

| graf                | bez pliku przyczyny | z luźnego pliku | nieodczytane | pomiar         |
|---------------------|---------------------|-----------------|--------------|----------------|
| `search`            | 0 z 3               | 0 z 1           | 0 z 4        | 2026-10-15, ×3 |
| `suggest_questions` | 0 z 1               | 0 z 1           | 0 z 2        | 2026-10-15, ×3 |
| `suggest_solution`  | 0 z 1               | 0 z 1           | 0 z 2        | 2026-10-15, ×3 |

Liczby to sprawy z błędem wśród spraw, których warunek dotyczy, w każdym z trzech przebiegów
na `gpt-6.1-sol`.

O czym pamiętać przy zmianach:

- Progu nie ma: każdy błąd to poprawka promptu. Sprawę poprawia się tylko wtedy, gdy błędna jest
  ona sama, nigdy pod wynik.
- Spis katalogu, nazwę pliku widocznego tylko w spisie i przyczynę wykluczoną przez wątek liczy
  raport, bez asercji; czy uwagi odróżniają stan kodu od instalacji klienta, czyta się w nich.
- Cytowania i odczyty ocena bierze z wyników narzędzi w rozmowie, nie z deklaracji modelu.
  Odczytana jest linia z wyniku `read_code_file` albo `read_code_symbol` we wcześniejszej turze;
  linia widziana tylko w wyniku szukania odczytana nie jest.
- Para spraw z wątkiem, w którym klient wyklucza jedną przyczynę, idzie tylko na `search`:
  pozostałe dwa grafy sięgają po kod wyłącznie przy komunikacie, wpisie z logu albo kodzie
  błędu. Nowy graf z narzędziami kodu to wpis w `graphs` spraw, które mają na nim iść.
- Wymaga zbudowanej paczki syntetycznej i ripgrepa na hoście, jak testy narzędzi kodu.
- KOSZTUJE: sprawa to pętla agenta z narzędziami, 3–6 tur modelu; osiem spraw (cztery
  w `search`, po dwie w `suggest_questions` i `suggest_solution`) na `gpt-6.1-sol` to szacunkowo
  0,2–0,3 USD
  (przebiegi z 2026-10-15 liczono razem z sekcją `search` zestawu wstrzyknięć: 0,49–0,57 USD
  za całość) i około dwóch minut. Jeden graf przez `-k <graf>`.
"""

import pytest

from tests._helpers.live import LiveUsageReport, live_generation_llm, remember_per_graph
from tests._helpers.scenarios.code import (
    CodeOutcomesOf,
    CodeReport,
    code_sections,
    measure_code_cases,
)

pytestmark = pytest.mark.llm_live

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = code_sections()


@pytest.fixture(scope="module")
def outcomes(
    request:       pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:    LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    code_report: CodeReport,           # wstrzykiwane przez pytest; raport ocen spraw
) -> CodeOutcomesOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu przeprowadza jego sprawy na żywym modelu i oddaje ich
    oceny. Sprawy grafu liczą się przy pierwszym teście, który o nie poprosi, i są zapamiętane
    na cały plik — razem z błędem, jeśli przebieg się nim skończył.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: outcomes("search") -> [CodeOutcome(case=CodeCase(case_id="k01", …), …), …]
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(
        lambda name: measure_code_cases(name, llm, live_usage, code_report)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_answer(graph: str, outcomes: CodeOutcomesOf) -> None:
    """Sprawdza, czy każda sprawa kończy się na żywym modelu wynikiem, który węzeł odpowiedzi
    przyjął: uwagami dla wdrożeniowca w `search`, pytaniami albo samymi uwagami
    w `suggest_questions`, propozycją albo samymi uwagami w `suggest_solution`.

    Wyłapuje prompt, przy którym model nie umie oddać odpowiedzi w kształcie narzędzia odpowiedzi
    nawet po poprawce: wdrożeniowiec dostaje wtedy błąd zamiast wyniku."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez wyniku — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_the_file_with_the_message_is_quoted_as_cause(
    graph:    str,
    outcomes: CodeOutcomesOf,
) -> None:
    """Sprawdza, czy w każdej sprawie, której komunikat stoi tylko w kodzie, model zacytował jako
    przyczynę plik, w którym ten komunikat stoi.

    Wyłapuje odpowiedź, która komunikat znajduje, ale przyczyny nie wskazuje, albo wskazuje ją
    w innym pliku: wdrożeniowiec nie dostaje na liście źródeł miejsca, które sprawę tłumaczy."""
    missing = [outcome for outcome in outcomes(graph) if outcome.missing_causes]

    assert not missing, (
        f"{graph}: bez pliku przyczyny — "
        + "; ".join(f"{o.case.label}: {', '.join(o.missing_causes)}" for o in missing)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_no_cause_is_quoted_when_the_message_is_nowhere(
    graph:    str,
    outcomes: CodeOutcomesOf,
) -> None:
    """Sprawdza, czy w każdej sprawie, której komunikatu nie ma w kodzie nigdzie, model nie
    zacytował niczego jako przyczyny — także pliku z podobnym komunikatem.

    Wyłapuje przyczynę z luźno powiązanego pliku: na liście źródeł wdrożeniowiec dostałby miejsce
    w kodzie, które jego sprawy nie tłumaczy, a wyglądałoby na przyczynę."""
    stray = [outcome for outcome in outcomes(graph) if outcome.stray_causes]

    assert not stray, (
        f"{graph}: przyczyna z luźnego pliku — "
        + "; ".join(f"{o.case.label}: {', '.join(o.stray_causes)}" for o in stray)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_quote_points_at_lines_read_before(graph: str, outcomes: CodeOutcomesOf) -> None:
    """Sprawdza, czy w każdej sprawie każde cytowanie kodu — przyczyna albo wykluczenie — wskazuje
    linie, które model w jednej z wcześniejszych tur przeczytał odczytem pliku albo symbolu.

    Wyłapuje cytowanie na ślepo, po samej linii z wyniku szukania albo z zakresu wybranego przed
    odczytem: przyczyna wskazana bez przeczytania warunku, który ją wywołuje."""
    unread = [outcome for outcome in outcomes(graph) if outcome.unread]

    assert not unread, (
        f"{graph}: cytowania linii nieodczytanych — "
        + "; ".join(f"{o.case.label}: {', '.join(o.unread)}" for o in unread)
    )
