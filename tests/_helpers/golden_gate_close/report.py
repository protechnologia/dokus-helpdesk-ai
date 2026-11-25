"""
Description:
Raport bramki zamknięcia na prawdziwych zamknięciach: `GateCloseReport` zbiera oceny zamknięć
z jednego przebiegu pytesta i składa wydruk, który pytest pokazuje po testach. Na górze
liczniki — razem, na grupę wpisów, dla wpisów wątpliwych i na warstwę doboru — potem czas
bramki z doliczoną anonimizacją, a niżej każde zamknięcie z oceną. Przy zamknięciu ocenionym
inaczej niż etykiety stoją etykiety z powodem i pola werdyktu w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `gate_close_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola werdyktu wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy.
- Wydruk cytuje uzasadnienia modelu, a te cytują wątki korpusu po anonimizacji: zostaje na
  ekranie, do CLAUDE.md idą same liczby.
"""

from collections.abc import Sequence

from tests._helpers.golden_gate_close.constants import (
    ANONYMIZATION_MAX_SECONDS,
    ANONYMIZATION_MEDIAN_SECONDS,
    GROUP_LABELS,
    STRATA,
)
from tests._helpers.golden_gate_close.helper import timing_summary
from tests._helpers.golden_gate_close.models.gate_close_outcome import GateCloseOutcome
from tests._helpers.scenarios.injections import field_lines


class GateCloseReport:
    """
    Description:
    Zbiera oceny zamknięć z zestawu bramki zamknięcia w jednym przebiegu pytesta i składa z nich
    wydruk: liczniki fałszywych alarmów i przepuszczeń, czas bramki i każde zamknięcie z oceną.

    Do czego:
    Test zalicza zestaw po liczbie złych werdyktów, ale czy zły werdykt to błąd bramki, czy
    etykiety, mówią dopiero uzasadnienie modelu i powód etykiety obok siebie. Wydruk jest po to,
    żeby je przeczytać przy każdym pomiarze.

    Flow:
        1. Pomiar dostaje raport przez fixture `gate_close_report` i woła `record()` raz na
           zamknięcie.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            GateCloseReport bez zgłoszonych zamknięć
        """
        self._outcomes: list[GateCloseOutcome] = []

    def record(
        self,
        outcome: GateCloseOutcome,  # np. judge_gate_close_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednego zamknięcia.

        Example args:
            outcome=GateCloseOutcome(case=GoldenGateCloseCase(ticket_id="33605", …), …)

        Example result:
            None — zamknięcie jest w raporcie
        """
        self._outcomes.append(outcome)

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: liczniki razem, na grupę, dla wpisów wątpliwych i na warstwę, czas bramki,
        liczbę poprawek, a niżej zamknięcia w kolejności zgłoszenia. Zamknięcie zgodne z etykietami
        to jedna linia; niezgodne ma pod sobą etykiety z powodem i pola werdyktu. Pusty raport daje
        pustą listę.

        Example args:
            (brak)

        Example result:
            ["razem: fałszywych alarmów 1 z 61, przepuszczeń 2 z 59, nie do przyjęcia 0",
             "    widać problem i rozwiązanie: fałszywych alarmów 1 z 61, nie do przyjęcia 0",
             …,
             "czas bramki: mediana 3,1 s, p90 5,4 s, maks. 9,8 s; …",
             "poprawek odpowiedzi: 0",
             "    33605 (random, nie widać rozwiązania): PRZEPUSZCZENIE; poprawek 0; 3,2 s",
             "        problem: tak — …",
             …]
        """
        outcomes = self._outcomes

        # --- pusty raport: przebieg bez pomiaru bramki zamknięcia ---
        if not outcomes:
            return []

        lines = [f"razem: {_counts(outcomes)}"]

        # --- liczniki na grupę wpisów, w kolejności grup ---
        for group, label in GROUP_LABELS.items():
            in_group = [outcome for outcome in outcomes if outcome.case.group == group]
            if in_group:
                lines.append(f"    {label}: {_counts(in_group)}")

        # --- wpisy wątpliwe: ile złych werdyktów stoi przy przypadkach granicznych ---
        doubtful = [outcome for outcome in outcomes if outcome.case.doubtful]
        if doubtful:
            lines.append(f"    wpisy wątpliwe: {_counts(doubtful)}")

        # --- liczniki na warstwę doboru ---
        for stratum in STRATA:
            in_stratum = [outcome for outcome in outcomes if outcome.case.stratum == stratum]
            if in_stratum:
                lines.append(f"    warstwa {stratum}: {_counts(in_stratum)}")

        lines.append(_timing_line([outcome.seconds for outcome in outcomes]))
        lines.append(f"poprawek odpowiedzi: {sum(outcome.retries for outcome in outcomes)}")

        # --- zamknięcia: zgodne jedną linią, niezgodne z etykietami i werdyktem ---
        for outcome in outcomes:
            lines.append(
                f"    {outcome.case.label}: {outcome.assessment}; poprawek {outcome.retries}; "
                f"{_seconds(outcome.seconds)} s"
            )

            if outcome.assessment == "zgodny":
                continue

            lines.append(f"        problem: {_label(outcome.case.problem_visible)} — "
                         f"{outcome.case.problem_reason}")
            lines.append(f"        rozwiązanie: {_label(outcome.case.action_visible)} — "
                         f"{outcome.case.action_reason}")
            lines.append(f"        rodzaj: {outcome.case.kind}")
            lines.extend(field_lines(outcome.fields))

        return lines


def _counts(
    outcomes: Sequence[GateCloseOutcome],  # np. oceny zamknięć jednej grupy
) -> str:
    """
    Description:
    Liczniki do raportu: fałszywe alarmy wśród wpisów, które mają przejść, przepuszczenia wśród
    tych, które mają zostać zablokowane, i odpowiedzi nie do przyjęcia. Licznik bez wpisów
    w mianowniku nie jest wypisywany, bo „0 z 0” niczego nie mówi.

    Example args:
        outcomes=[GateCloseOutcome(case=GoldenGateCloseCase(…), answer="block", …), …]

    Example result:
        "fałszywych alarmów 1 z 61, przepuszczeń 2 z 59, nie do przyjęcia 0"
    """
    should_pass  = [outcome for outcome in outcomes if outcome.case.expected == "pass"]
    should_block = [outcome for outcome in outcomes if outcome.case.expected == "block"]
    parts: list[str] = []

    # --- fałszywe alarmy: tylko gdy są wpisy, które mają przejść ---
    if should_pass:
        false_alarms = sum(outcome.false_alarm for outcome in should_pass)
        parts.append(f"fałszywych alarmów {false_alarms} z {len(should_pass)}")

    # --- przepuszczenia: tylko gdy są wpisy, które mają zostać zablokowane ---
    if should_block:
        misses = sum(outcome.miss for outcome in should_block)
        parts.append(f"przepuszczeń {misses} z {len(should_block)}")

    parts.append(f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}")

    return ", ".join(parts)


def _timing_line(
    seconds: Sequence[float],  # np. [2.1, 3.4, 9.8] — czasy spraw bramki
) -> str:
    """
    Description:
    Linia z czasem bramki i z czasem razem z anonimizacją wątku. Test idzie bez anonimizatora,
    więc jego czas raport dolicza z pomiaru z 2026-10-19: mediana do mediany (wynik przybliżony,
    stąd „około”) i maksimum do maksimum (górna granica, stąd „do”).

    Example args:
        seconds=[2.0, 3.0, 9.8]

    Example result:
        "czas bramki: mediana 3,0 s, p90 9,8 s, maks. 9,8 s; z anonimizacją (pomiar 2026-10-19:
         mediana 2,0 s, maks. 6,5 s): mediana około 5,0 s, maks. do 16,3 s"
    """
    summary = timing_summary(seconds)

    line = (
        f"czas bramki: mediana {_seconds(summary.median)} s, p90 {_seconds(summary.p90)} s, "
        f"maks. {_seconds(summary.maximum)} s; z anonimizacją (pomiar 2026-10-19: mediana "
        f"{_seconds(ANONYMIZATION_MEDIAN_SECONDS)} s, maks. {_seconds(ANONYMIZATION_MAX_SECONDS)}"
        f" s): mediana około {_seconds(summary.median + ANONYMIZATION_MEDIAN_SECONDS)} s, maks. do "
        f"{_seconds(summary.maximum + ANONYMIZATION_MAX_SECONDS)} s"
    )

    return line


def _seconds(value: float) -> str:  # np. 3.25
    """
    Description:
    Sekundy z jednym miejscem po przecinku, z polskim przecinkiem.

    Example args:
        value=3.25

    Example result:
        "3,2"
    """
    return f"{value:.1f}".replace(".", ",")


def _label(visible: bool) -> str:  # np. True
    """
    Description:
    Etykieta reguły słowem: czy z treści wynika to, czego reguła wymaga.

    Example args:
        visible=True

    Example result:
        "tak"
    """
    return "tak" if visible else "nie"
