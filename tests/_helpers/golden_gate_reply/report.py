"""
Description:
Raport bramki wysyłki na prawdziwych wiadomościach: `GateReplyReport` zbiera oceny wiadomości
z jednego przebiegu pytesta i składa wydruk, który pytest pokazuje po testach. Na górze
liczniki — razem, przepuszczenia na regułę, wpisy wątpliwe i warstwy doboru — potem czas bramki
z doliczoną anonimizacją, a niżej każda wiadomość z oceną. Przy wiadomości ocenionej inaczej niż
etykiety stoją łamane reguły z powodem, wątpliwość oceniającego i pola werdyktu w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `gate_reply_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola werdyktu wypisuje `field_lines()` z helpera wstrzyknięć, a czas liczy `timing_summary()`
  z helpera bramki zamknięcia, wspólne dla raportów.
- Wydruk cytuje uzasadnienia modelu, a te cytują wiadomości korpusu po anonimizacji: zostaje na
  ekranie, do CLAUDE.md idą same liczby.
"""

from collections.abc import Sequence

from tests._helpers.golden_gate_close import timing_summary
from tests._helpers.golden_gate_reply.constants import (
    ANONYMIZATION_MAX_SECONDS,
    ANONYMIZATION_MEAN_SECONDS,
    RULES,
    STRATA,
)
from tests._helpers.golden_gate_reply.models.gate_reply_outcome import GateReplyOutcome
from tests._helpers.scenarios.injections import field_lines


class GateReplyReport:
    """
    Description:
    Zbiera oceny wiadomości z zestawu bramki wysyłki w jednym przebiegu pytesta i składa z nich
    wydruk: liczniki fałszywych alarmów i przepuszczeń, czas bramki i każdą wiadomość z oceną.

    Do czego:
    Test zalicza zestaw po liczbie złych werdyktów, ale czy zły werdykt to błąd bramki, czy
    etykiety, mówią dopiero uzasadnienie modelu i powód etykiety obok siebie. Wydruk jest po to,
    żeby je przeczytać przy każdym pomiarze.

    Flow:
        1. Pomiar dostaje raport przez fixture `gate_reply_report` i woła `record()` raz na
           wiadomość.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            GateReplyReport bez zgłoszonych wiadomości
        """
        self._outcomes: list[GateReplyOutcome] = []

    def record(
        self,
        outcome: GateReplyOutcome,  # np. judge_gate_reply_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej wiadomości.

        Example args:
            outcome=GateReplyOutcome(case=GoldenGateReplyCase(ticket_id="23921", …), …)

        Example result:
            None — wiadomość jest w raporcie
        """
        self._outcomes.append(outcome)

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: liczniki razem, przepuszczenia na regułę, liczniki dla wpisów wątpliwych
        i na warstwę, czas bramki, liczbę poprawek, a niżej wiadomości w kolejności pomiaru.
        Wiadomość zgodna z etykietami to jedna linia; niezgodna ma pod sobą łamane reguły
        z powodem, wątpliwość oceniającego i pola werdyktu. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["razem: fałszywych alarmów 3 z 108, przepuszczeń 4 z 71, nie do przyjęcia 0",
             "    reguła 5: przepuszczeń 3 z 58",
             …,
             "czas bramki: mediana 2,1 s, p90 3,4 s, maks. 5,0 s; …",
             "poprawek odpowiedzi: 0",
             "    23921/2 (keywords, reguły 6): PRZEPUSZCZENIE; poprawek 0; 2,4 s",
             "        reguła 6: Wiadomość podaje w treści hasło do nowego konta.",
             …]
        """
        outcomes = self._outcomes

        # --- pusty raport: przebieg bez pomiaru bramki wysyłki ---
        if not outcomes:
            return []

        lines = [f"razem: {_counts(outcomes)}"]

        # --- przepuszczenia na regułę: wiadomość łamiąca dwie reguły liczy się przy obu ---
        for rule in RULES:
            breaking = [outcome for outcome in outcomes if rule in outcome.case.broken_rules]
            if breaking:
                misses = sum(outcome.miss for outcome in breaking)
                lines.append(f"    reguła {rule}: przepuszczeń {misses} z {len(breaking)}")

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

        # --- wiadomości: zgodne jedną linią, niezgodne z etykietami i werdyktem ---
        for outcome in outcomes:
            lines.append(
                f"    {outcome.case.label}: {outcome.assessment}; poprawek {outcome.retries}; "
                f"{_seconds(outcome.seconds)} s"
            )

            if outcome.assessment == "zgodny":
                continue

            for violation in outcome.case.violations:
                lines.append(f"        reguła {violation.rule}: {violation.reason}")
            if outcome.case.doubt:
                lines.append(f"        wątpliwość: {outcome.case.doubt}")
            lines.extend(field_lines(outcome.fields))

        return lines


def _counts(
    outcomes: Sequence[GateReplyOutcome],  # np. oceny wiadomości jednej warstwy
) -> str:
    """
    Description:
    Liczniki do raportu: fałszywe alarmy wśród wiadomości poprawnych, przepuszczenia wśród
    łamiących regułę i odpowiedzi nie do przyjęcia. Licznik bez wpisów w mianowniku nie jest
    wypisywany, bo „0 z 0” niczego nie mówi.

    Example args:
        outcomes=[GateReplyOutcome(case=GoldenGateReplyCase(…), answer="block", …), …]

    Example result:
        "fałszywych alarmów 3 z 108, przepuszczeń 4 z 71, nie do przyjęcia 0"
    """
    should_pass  = [outcome for outcome in outcomes if outcome.case.expected == "pass"]
    should_block = [outcome for outcome in outcomes if outcome.case.expected == "block"]
    parts: list[str] = []

    # --- fałszywe alarmy: tylko gdy są wiadomości poprawne ---
    if should_pass:
        false_alarms = sum(outcome.false_alarm for outcome in should_pass)
        parts.append(f"fałszywych alarmów {false_alarms} z {len(should_pass)}")

    # --- przepuszczenia: tylko gdy są wiadomości łamiące regułę ---
    if should_block:
        misses = sum(outcome.miss for outcome in should_block)
        parts.append(f"przepuszczeń {misses} z {len(should_block)}")

    parts.append(f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}")

    return ", ".join(parts)


def _timing_line(
    seconds: Sequence[float],  # np. [2.1, 3.4, 5.0] — czasy spraw bramki
) -> str:
    """
    Description:
    Linia z czasem bramki i z czasem razem z anonimizacją wiadomości. Test idzie bez
    anonimizatora, więc jego czas raport dolicza z pomiaru z 2026-10-19 na krótkich tekstach:
    średnią do mediany (wynik przybliżony, stąd „około”) i maksimum do maksimum (górna granica,
    stąd „do”).

    Example args:
        seconds=[2.0, 3.0, 5.0]

    Example result:
        "czas bramki: mediana 3,0 s, p90 5,0 s, maks. 5,0 s; z anonimizacją (pomiar 2026-10-19,
         krótki tekst: średnio 1,0 s, maks. 3,8 s): mediana około 4,0 s, maks. do 8,8 s"
    """
    summary = timing_summary(seconds)

    line = (
        f"czas bramki: mediana {_seconds(summary.median)} s, p90 {_seconds(summary.p90)} s, "
        f"maks. {_seconds(summary.maximum)} s; z anonimizacją (pomiar 2026-10-19, krótki tekst: "
        f"średnio {_seconds(ANONYMIZATION_MEAN_SECONDS)} s, maks. "
        f"{_seconds(ANONYMIZATION_MAX_SECONDS)} s): mediana około "
        f"{_seconds(summary.median + ANONYMIZATION_MEAN_SECONDS)} s, maks. do "
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
