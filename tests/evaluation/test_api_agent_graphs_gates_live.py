"""
Description:
Scenariusze ewaluacyjne bramek na żywym modelu (p. 59): czy bramka blokuje wejście, które łamie
regułę klienta, i przepuszcza poprawne — także takie, które na łamiące tylko wygląda. Zestaw leży
w `data/safe/golden/gates.json`, z sekcją na bramkę; na każdą regułę zestawu domyślnego ma trzy
wejścia: łamiące, poprawnego bliźniaka i pułapkę. Bramka bez sekcji nie ma tu testów.

Każda bramka z sekcją w zestawie przechodzi przez trzy testy:

| test                                    | co sprawdza                                     |
|-----------------------------------------|-------------------------------------------------|
| `test_every_case_gets_an_accepted_verdict` | każda sprawa kończy się werdyktem            |
| `test_no_correct_input_is_blocked`      | żadne poprawne wejście ani pułapka nie są blokowane |
| `test_no_breaking_input_passes`         | żadne łamiące wejście nie przechodzi            |

Pomiary:

| bramka       | fałszywe alarmy | przepuszczenia | pomiar                                         |
|--------------|-----------------|----------------|------------------------------------------------|
| `gate_reply` | 0 z 6           | 0 z 3          | 2026-10-14, `gpt-6.1-sol`, w dwóch przebiegach |
| `gate_close` | 0 z 4           | 0 z 2          | 2026-10-14, `gpt-6.1-sol`, w dwóch przebiegach |

Pierwszy pomiar `gate_reply` dał w obu przebiegach fałszywy alarm na pułapce g06: bramka uznała
cytat komunikatu z ekranu („Ups! Coś poszło nie tak.”) za potoczne słownictwo wiadomości. Po
zdaniu o cytatach w prompcie bramki (cudze słowa nie są słownictwem wiadomości) g06 przechodzi.

O czym pamiętać przy zmianach:

- Progu nie ma: każdy fałszywy alarm i każde przepuszczenie to poprawka promptu albo reguły.
  Sprawę poprawia się tylko wtedy, gdy błędna jest ona sama, nigdy pod wynik.
- Fałszywe alarmy i przepuszczenia to osobne testy, bo fałszywy alarm boli bardziej: uczy
  wdrożeniowców klikać furtkę odruchowo, a wtedy bramka nie działa już wcale.
- Reguły bierze się z zestawu domyślnego bramki, tak jak trasa. Sekcja zapisuje wersję zestawu,
  pod którą ją napisano; przy innej wersji test kończy się błędem, zanim zawoła model.
- Nowa bramka to sekcja w zestawie.
- Liczy się sam werdykt. Czy bramka zablokowała z właściwego powodu, mówi uzasadnienie
  w raporcie, który pytest wypisuje po przebiegu; czyta się je przy pierwszym pomiarze i przy
  każdej zmianie wyniku.
- KOSZTUJE: sprawa to jedna tura modelu. `gate_reply` ma dziewięć spraw: na `gpt-6.1-sol`
  0,02 USD i kilka sekund; `gate_close` sześć: 0,01 USD.
"""


import pytest

from tests._helpers.live import (
    LiveUsageReport,
    live_generation_llm,
    remember_per_graph,
)
from tests._helpers.scenarios.gates import (
    GateOutcomesOf,
    GateReport,
    gate_sections,
    measure_gate_cases,
)

pytestmark = pytest.mark.llm_live

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = gate_sections()


@pytest.fixture(scope="module")
def outcomes(
    request:     pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:  LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    gate_report: GateReport,             # wstrzykiwane przez pytest; raport ocen spraw
) -> GateOutcomesOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy bramki przeprowadza jej sprawy na żywym modelu i oddaje ich
    oceny. Sprawy bramki liczą się przy pierwszym teście, który o nie poprosi, i są zapamiętane
    na cały plik — razem z błędem, jeśli przebieg się nim skończył.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: outcomes("gate_reply") -> [GateOutcome(case=GateCase(case_id="g01", …), …), …]
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(lambda name: measure_gate_cases(name, llm, live_usage, gate_report))


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_verdict(graph: str, outcomes: GateOutcomesOf) -> None:
    """Sprawdza, czy każda sprawa bramki kończy się na żywym modelu werdyktem, który węzeł
    odpowiedzi przyjął.

    Wyłapuje prompt, przy którym model nie umie oddać werdyktu w kształcie narzędzia odpowiedzi
    nawet po poprawce: helpdesk dostaje wtedy 503 i decyduje bez bramki."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez werdyktu — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_no_correct_input_is_blocked(graph: str, outcomes: GateOutcomesOf) -> None:
    """Sprawdza, czy bramka nie blokuje żadnego poprawnego wejścia — ani bliźniaka łamiącego, ani
    pułapki.

    Wyłapuje bramkę, która blokuje wiadomość za samo słowo kojarzone z regułą, na przykład za
    „hasło” w prośbie, żeby hasła nie podawać, albo za cytat komunikatu z ekranu: takie alarmy
    uczą wdrożeniowców obchodzić bramkę bez czytania."""
    alarms = [outcome for outcome in outcomes(graph) if outcome.false_alarm]

    assert not alarms, (
        f"{graph}: fałszywych alarmów {len(alarms)} — "
        + ", ".join(outcome.case.label for outcome in alarms)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_no_breaking_input_passes(graph: str, outcomes: GateOutcomesOf) -> None:
    """Sprawdza, czy bramka nie przepuszcza żadnego wejścia, które łamie regułę.

    Wyłapuje bramkę, która nie widzi złamania reguły: prośba o hasło, potoczne słowa albo zwrot
    na „ty” wychodzą wtedy do klienta bez ostrzeżenia."""
    misses = [outcome for outcome in outcomes(graph) if outcome.miss]

    assert not misses, (
        f"{graph}: przepuszczeń {len(misses)} — "
        + ", ".join(outcome.case.label for outcome in misses)
    )
