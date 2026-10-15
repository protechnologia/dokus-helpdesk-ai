"""
Description:
Spójność zestawu scenariuszy „pytań już nie trzeba” (`data/safe/golden/questions.json`) bez
modelu: czy sprawy dotyczą grafu, który umie oddać brak pytań, i czy zestaw mierzy obie strony.
Test na żywym modelu z takim zestawem byłby zielony, nic nie mierząc, więc te warunki pilnuje się
w domyślnym `pytest`.

| warunek                                       | czym grozi jego brak                        |
|-----------------------------------------------|---------------------------------------------|
| sekcja nazywa graf, którego wynik bywa        | sekcja, której nikt nie uruchomi, albo graf, |
| pytaniami albo samymi uwagami                 | który brak pytań zgłasza błędem             |
| sprawy mają różne identyfikatory              | raport, w którym nie wiadomo, o którą chodzi |
| są sprawy z pytaniami i bez                   | zestaw mierzący tylko jedną stronę          |
| zgłoszenie ma kształt wątku                   | sprawa, która nie wygląda jak wejście trasy |
"""


import pytest

from tests._helpers.graphs import graph_module, graph_names, output_types
from tests._helpers.scenarios.questions import QuestionsCase, questions_sections

SECTIONS = questions_sections()


# Pary (graf, sprawa) zestawu, czytane przy imporcie: z nich powstają parametry testów.
CASES = [(graph, case) for graph, section in SECTIONS.items() for case in section.cases]


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_graph_that_can_answer_without_questions(graph: str) -> None:
    """Sprawdza, czy każda sekcja nazywa się jak katalog grafu, którego wynik bywa propozycją
    z pytaniami (pole `text`) albo samymi uwagami, bez tego pola.

    Wyłapuje sekcję z literówką w nazwie, której sprawy nie zostałyby nigdy sprawdzone, i sekcję
    grafu, który braku pytań nie umie oddać: ocena nie miałaby czego odróżniać."""
    assert graph in graph_names()

    module  = graph_module(graph)
    outputs = output_types(module)

    assert any("text" in output.model_fields for output in outputs)
    assert any("text" not in output.model_fields for output in outputs)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_a_section_measures_both_sides_with_unique_ids(graph: str) -> None:
    """Sprawdza, czy sekcja ma sprawy, w których pytania są potrzebne, i takie, w których nie są,
    a identyfikatory spraw się nie powtarzają.

    Wyłapuje zestaw mierzący jedną stronę: model, który zawsze pyta albo nigdy nie pyta,
    przeszedłby test drugiej strony bez żadnego sprawdzenia; i dwie sprawy o jednym
    identyfikatorze w raporcie."""
    cases = SECTIONS[graph].cases
    ids   = [case.case_id for case in cases]

    assert {case.questions for case in cases} == {True, False}
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    ("graph", "case"),
    CASES,
    ids=lambda value: getattr(value, "case_id", value),
)
def test_every_case_is_a_ticket_with_a_thread(graph: str, case: QuestionsCase) -> None:
    """Sprawdza, czy każda sprawa ma kształt wątku z `RawTicket.as_thread()`: nagłówek zgłoszenia,
    temat i opis zgłaszającego.

    Wyłapuje sprawę, która nie wygląda jak wejście trasy `/suggest`: model dostałby inny kształt
    niż na produkcji, a wynik nie mówiłby nic o prawdziwej sprawie."""
    assert case.text.startswith("ZGŁOSZENIE ")
    assert "\nTemat: " in case.text
    assert "\nOPIS ZGŁASZAJĄCEGO:\n" in case.text
