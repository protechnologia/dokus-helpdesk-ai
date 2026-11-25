"""
Description:
Pomiar bramki zamknięcia na prawdziwych zamknięciach z korpusu instancji (p. 33.2): fałszywe
alarmy i przepuszczenia na 120 zamknięciach zestawu `data/unsafe/golden/gate-close.json`. Wejście
bramki to wątek z `corpus/anonymized/` ucięty na zamknięciu, czyli to, co widział konsultant,
który zamykał zgłoszenie; werdykt porównuje się z etykietami oceniających, po jednej na regułę.

| test (`test_…`)                          | co liczy                       | próg               |
|------------------------------------------|--------------------------------|--------------------|
| `every_closing_gets_an_accepted_verdict` | zamknięcia bez werdyktu        | 0                  |
| `false_alarms_stay_within_the_threshold` | blokady spraw z obu regułami   | `MAX_FALSE_ALARMS` |
| `misses_stay_within_the_threshold`       | przepuszczenia w grupie blokad | `MAX_MISSES`       |
| `no_marker_is_malformed`                 | znaczniki przekręcone          | 0                  |

Grupy blokad: sprawa, z której nie wynika problem (reguła 1), nie wynika, co zrobiono
(reguła 2), obie naraz i powiadomienie, które bramka ma zablokować bez względu na reguły
(GAT-001). Wpisy wątpliwe liczą się w progach razem z resztą (decyzja 2026-11-25), a raport
podaje osobno, ile złych werdyktów stoi przy nich.

Co się dzieje po drodze:

1. `measure_gate_close_cases()` sprawdza wersję reguł i skrót każdego uciętego wątku, zanim
   zawoła model.
2. Zamknięcia idą przez graf `gate_close` na regułach z zestawu domyślnego, po 4 naraz, z czasem
   każdej sprawy; anonimizator to atrapa, bo wątki są już po anonimizacji.
3. Raport po przebiegu (fixture `gate_close_report`) podaje liczniki razem, na grupę, dla wpisów
   wątpliwych i na warstwę, czas bramki z doliczoną anonimizacją i pod każdym złym werdyktem
   etykiety z powodem i uzasadnienie modelu.

Pomiary (reguły w wersji 1, `gpt-6.1-sol`, dwa przebiegi):

| data       | fałszywe alarmy | przepuszczenia                        | czas: mediana, maks. |
|------------|-----------------|---------------------------------------|----------------------|
| 2026-11-25 | 18 i 19 z 61    | 2 z 59: reguła 1 1 z 1, powiad. 1 z 7 | 3,5 s, 7,2 i 8,2 s   |

Złe werdykty są prawie te same w obu przebiegach (17 fałszywych alarmów wspólnych, oba
przepuszczenia te same), a 10 fałszywych alarmów stoi przy wpisach wątpliwych. Bramka blokuje
konkretne wyjaśnienie albo przyczynę bez czynności i krótką czynność, której przedmiot wynika
z wątku, bo reguła 2 pyta tylko, „co zostało zrobione”; przy ostatniej reklamacji klienta bez
odpowiedzi ma za to rację wbrew etykietom. Przegląd i dalsze kroki: p. 33.2.3.

O czym pamiętać przy zmianach:

- Próg to gorszy wynik z dwóch przebiegów na tym samym modelu: model nie jest deterministyczny
  przy temperaturze 0. Zmiana promptu bramki albo reguł to ten pomiar od nowa, dwa przebiegi.
- Czasu test nie sprawdza, tylko go podaje: cierpliwość UI helpdesku ustala wpięcie (p. 38).
- Zestaw i korpus to dane klientów, poza repo: bez nich testy się pomija. Raport cytuje
  uzasadnienia modelu, więc zostaje na ekranie, a do CLAUDE.md idą same liczby.
- KOSZTUJE: sprawa to jedna tura modelu na wątku do kilkunastu tysięcy znaków. Cały zestaw na
  `gpt-6.1-sol` to 0,51 USD przy pierwszym przebiegu i 0,17 USD przy drugim, z początkiem
  żądania z cache, oraz około 2 minut.
"""

import pytest

from tests._helpers.golden_gate_close import (
    ANONYMIZED_DIR,
    BLOCK_GROUPS,
    GOLDEN_FILE,
    GROUP_LABELS,
    MAX_FALSE_ALARMS,
    MAX_MISSES,
    GateCloseOutcome,
    GateCloseReport,
    golden_gate_close_cases,
    measure_gate_close_cases,
)
from tests._helpers.live import LiveUsageReport, live_generation_llm

pytestmark = [
    pytest.mark.llm_live,
    pytest.mark.skipif(
        not GOLDEN_FILE.is_file() or not ANONYMIZED_DIR.is_dir(),
        reason="zestawu bramki zamknięcia i wątków korpusu nie ma w repo",
    ),
]


@pytest.fixture(scope="module")
def outcomes(
    request:           pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:        LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    gate_close_report: GateCloseReport,        # wstrzykiwane przez pytest; raport ocen zamknięć
) -> list[GateCloseOutcome]:
    """
    Description:
    Przeprowadza wszystkie zamknięcia zestawu przez bramkę na żywym modelu i oddaje ich oceny.
    Liczy się raz na plik: wszystkie testy dostają te same oceny, a błąd pomiaru pytest
    zapamiętuje i zgłasza każdemu testowi bez ponownego wołania modelu.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        [GateCloseOutcome(case=GoldenGateCloseCase(ticket_id="33605", …), answer="pass", …), …]
    """
    llm = live_generation_llm(request.config)

    return measure_gate_close_cases(golden_gate_close_cases(), llm, live_usage, gate_close_report)


def test_every_closing_gets_an_accepted_verdict(outcomes: list[GateCloseOutcome]) -> None:
    """Sprawdza, czy każde zamknięcie z zestawu kończy się werdyktem, który węzeł odpowiedzi
    przyjął.

    Wyłapuje wątek, na którym model nie umie oddać werdyktu w kształcie narzędzia odpowiedzi
    nawet po poprawce, na przykład bardzo długi albo z kanału „Automat mailowy”: helpdesk
    dostaje wtedy 503 i zamyka bez bramki."""
    rejected = [outcome.case.label for outcome in outcomes if outcome.rejected]

    assert not rejected, f"bez werdyktu: {', '.join(rejected)}"


def test_false_alarms_stay_within_the_threshold(outcomes: list[GateCloseOutcome]) -> None:
    """Sprawdza, czy bramka blokuje najwyżej `MAX_FALSE_ALARMS` spraw z tych, które spełniają
    obie reguły: z treści wynika problem i to, co zrobiono.

    Wyłapuje bramkę, która blokuje poprawne zamknięcia, na przykład za krótkie rozwiązanie albo
    za znaczniki anonimizacji w miejscu danych: fałszywy alarm uczy wdrożeniowców klikać furtkę
    odruchowo, a wtedy bramka nie działa już wcale."""
    alarms = [outcome.case.label for outcome in outcomes if outcome.false_alarm]

    assert len(alarms) <= MAX_FALSE_ALARMS, (
        f"fałszywych alarmów {len(alarms)} przy progu {MAX_FALSE_ALARMS}: {', '.join(alarms)}"
    )


@pytest.mark.parametrize("group", BLOCK_GROUPS)
def test_misses_stay_within_the_threshold(
    group:    str,                     # np. "rule2"
    outcomes: list[GateCloseOutcome],  # wstrzykiwane przez pytest; oceny zamknięć
) -> None:
    """Sprawdza, czy w danej grupie blokad bramka przepuszcza najwyżej tyle wpisów, ile pozwala
    `MAX_MISSES`: osobno sprawy bez widocznego problemu, bez widocznej czynności, bez obu
    i powiadomienia.

    Wyłapuje bramkę, która przepuszcza zamknięcie zdaniem „problem rozwiązany” albo „omówione
    telefonicznie”: do korpusu trafia wtedy karta bez wiedzy, czyli dokładnie to, czemu bramka
    ma zapobiegać. Przy powiadomieniu wyłapuje bramkę, która przepuszcza rozsyłkę, choć GAT-001
    każe ją blokować."""
    misses = [
        outcome.case.label
        for outcome in outcomes
        if outcome.case.group == group and outcome.miss
    ]

    assert len(misses) <= MAX_MISSES[group], (
        f"{GROUP_LABELS[group]}: przepuszczeń {len(misses)} przy progu {MAX_MISSES[group]}: "
        + ", ".join(misses)
    )


def test_no_marker_is_malformed(outcomes: list[GateCloseOutcome]) -> None:
    """Sprawdza, czy w uzasadnieniu i wskazówce każdego werdyktu napisy w klamrach są
    znacznikami anonimizacji albo placeholderami z promptu, bez odmiany i bez zmiany liter.

    Wyłapuje werdykt, w którym model odmienił znacznik z wątku („{NAZWISKA}”) albo wymyślił
    własny: wdrożeniowiec nie wie wtedy, o którą daną chodzi, a anonimizacja przestaje być
    widoczna."""
    malformed = [
        f"{outcome.case.label}: {outcome.malformed}" for outcome in outcomes if outcome.malformed
    ]

    assert not malformed, f"przekręcone znaczniki — {', '.join(malformed)}"
