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


import pytest

from tests._helpers.live import (
    LiveUsageReport,
    live_generation_llm,
    remember_per_graph,
)
from tests._helpers.scenarios.polish import (
    PolishOutcomesOf,
    PolishReport,
    measure_polish_cases,
    polish_sections,
)

pytestmark = pytest.mark.llm_live

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = polish_sections()


@pytest.fixture(scope="module")
def outcomes(
    request:       pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:    LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    polish_report: PolishReport,           # wstrzykiwane przez pytest; raport ocen spraw
) -> PolishOutcomesOf:
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

    return remember_per_graph(
        lambda name: measure_polish_cases(name, llm, live_usage, polish_report)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_text(graph: str, outcomes: PolishOutcomesOf) -> None:
    """Sprawdza, czy każda sprawa „Popraw” kończy się na żywym modelu tekstem, który węzeł
    odpowiedzi przyjął.

    Wyłapuje prompt, przy którym model nie umie oddać tekstu narzędziem odpowiedzi nawet po
    poprawce: wdrożeniowiec dostaje wtedy błąd zamiast poprawionej wiadomości."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez tekstu — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_colloquial_words_disappear(graph: str, outcomes: PolishOutcomesOf) -> None:
    """Sprawdza, czy w żadnym poprawionym tekście nie zostaje słowo potoczne z notatek.

    Wyłapuje „Popraw”, które przepisuje notatki prawie dosłownie: wiadomość z „śmiga” albo
    „sorki” wychodzi do klienta, choć zasady stylu każą pisać bez potocznego słownictwa."""
    left = [outcome for outcome in outcomes(graph) if outcome.colloquial]

    assert not left, (
        f"{graph}: słowa potoczne zostały — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in left)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_facts_from_the_notes_stay(graph: str, outcomes: PolishOutcomesOf) -> None:
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
def test_no_numbers_or_names_are_added(graph: str, outcomes: PolishOutcomesOf) -> None:
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
