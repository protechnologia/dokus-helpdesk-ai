"""
Description:
Scenariusze ewaluacyjne czytania znalezionego materiału na żywym modelu (p. 59): czy grafy
z narzędziami wiedzy (`search`, `suggest_questions`, `suggest_solution`) czytają to, co znalazły —
przy jednym objawie z trzema przyczynami karty wszystkich trzech spraw. Obok liczniki: czy wynik
nazywa przyczyny, czy uwagi nazywają przyczynę wykluczoną przez klienta, czy model czyta właściwą
sekcję instrukcji, a nie dystraktor, i czy w sprawie organizacyjnej `search` nie sięga po kod.
Zestaw leży w `data/safe/golden/reading.json`; materiał to atrapy narzędzi, których wyszukiwania
oddają zawsze ten sam wynik, więc test mierzy czytanie, nie szukanie.

Każdy graf, który sprawy wymieniają w `graphs`, przechodzi przez dwa testy:

| test                                      | co sprawdza                                     |
|-------------------------------------------|-------------------------------------------------|
| `test_every_case_gets_an_accepted_answer` | każda sprawa kończy się wynikiem                |
| `test_the_found_material_is_read`         | wymagane źródła stoją na liście źródeł          |

Pomiary:

| graf                | nieprzeczytane | pomiar                                     |
|---------------------|----------------|--------------------------------------------|
| `search`            | 0 z 2          | 2026-10-15, `gpt-6.1-sol`, pięć przebiegów |
| `suggest_questions` | 0 z 2          | 2026-10-15, `gpt-6.1-sol`, pięć przebiegów |
| `suggest_solution`  | 0 z 1          | 2026-10-15, `gpt-6.1-sol`, pięć przebiegów |

Licznik przyczyny wykluczonej w dwóch pierwszych przebiegach liczył linie, które mówiły, że
przyczyny nie wykluczono, a wątek c02 załącznika nie wykluczał. Po mocniejszym fakcie w wątku,
wariantach stojących w jednej sprawie i pominięciu zaprzeczeń oba grafy wykluczyły 90003 wprost,
a licznik to policzył. W czwartym przebiegu model wykluczył „wariant dużego załącznika” bez
numeru sprawy i licznik tego nie policzył, więc fakt dostał warianty zapisane słowami modelu.

O czym pamiętać przy zmianach:

- Progu nie ma: każde nieprzeczytane źródło to poprawka promptu. Sprawę poprawia się tylko
  wtedy, gdy błędna jest ona sama, nigdy pod wynik.
- Nazwane przyczyny, przyczyna wykluczona, sekcje instrukcji i wywołania narzędzi kodu to
  liczniki w raporcie, bez asercji; licznik wykluczenia liczy słowa, więc uwagi czyta się
  w raporcie.
- KOSZTUJE: sprawa to pętla agenta z narzędziami, kilka tur modelu; dziewięć spraw na trzech
  grafach to 0,22–0,34 USD i 1,5–2 minuty.
"""

import pytest

from tests._helpers.live import LiveUsageReport, live_generation_llm, remember_per_graph
from tests._helpers.scenarios.reading import (
    ReadingOutcomesOf,
    ReadingReport,
    measure_reading_cases,
    reading_sections,
)

pytestmark = pytest.mark.llm_live

# Sekcje zestawu (graf → sprawy z pola `graphs`), czytane przy imporcie: z nich powstają
# parametry testów.
SECTIONS = reading_sections()


@pytest.fixture(scope="module")
def outcomes(
    request:        pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:     LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    reading_report: ReadingReport,          # wstrzykiwane przez pytest; raport ocen spraw
) -> ReadingOutcomesOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu przeprowadza jego sprawy na żywym modelu i oddaje ich
    oceny. Sprawy grafu liczą się przy pierwszym teście, który o nie poprosi, i są zapamiętane
    na cały plik — razem z błędem, jeśli przebieg się nim skończył.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: outcomes("search") -> [ReadingOutcome(case=ReadingCase(…), …)]
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(
        lambda name: measure_reading_cases(name, llm, live_usage, reading_report)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_answer(graph: str, outcomes: ReadingOutcomesOf) -> None:
    """Sprawdza, czy każda sprawa kończy się na żywym modelu wynikiem, który węzeł odpowiedzi
    przyjął: uwagami, propozycją albo samymi uwagami bez propozycji.

    Wyłapuje prompt, przy którym model nie umie oddać odpowiedzi w kształcie narzędzia
    odpowiedzi nawet po poprawce: wdrożeniowiec dostaje wtedy błąd zamiast wyniku."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez wyniku — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_the_found_material_is_read(graph: str, outcomes: ReadingOutcomesOf) -> None:
    """Sprawdza, czy w każdej sprawie, która wymaga przeczytania materiału, każde wymagane źródło —
    tu karty trzech spraw o jednym objawie i trzech różnych przyczynach — stoi na liście źródeł,
    czyli model je odczytał, a nie tylko znalazł.

    Wyłapuje agenta, który przy zgodnym objawie czyta jedną kartę i kończy: wynik stoi wtedy na
    jednej przyczynie z trzech, a dwóch pozostałych wdrożeniowiec nie zobaczy."""
    unread = [outcome for outcome in outcomes(graph) if outcome.unread]

    assert not unread, (
        f"{graph}: nieprzeczytane — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in unread)
    )
