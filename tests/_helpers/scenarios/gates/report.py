"""
Description:
Raport scenariuszy bramek: `GateReport` zbiera oceny spraw z jednego przebiegu pytesta
i składa wydruk, który pytest pokazuje po testach — fałszywe alarmy i przepuszczenia na
bramkę i na regułę, a niżej każdą sprawę z oceną i polami werdyktu w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `gate_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy, więc zmiana wydruku pól dotyczy wszystkich czterech.
"""

from collections.abc import Sequence

from tests._helpers.scenarios.gates.models.gate_outcome import GateOutcome
from tests._helpers.scenarios.injections import field_lines


class GateReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy bramek w jednym przebiegu pytesta i składa z nich wydruk:
    dla każdej bramki linię z liczbą fałszywych alarmów i przepuszczeń, pod nią te same liczby
    na każdą regułę, a niżej każdą sprawę z oceną i polami werdyktu w całości.

    Do czego:
    Test zalicza zestaw po werdykcie, ale czy bramka zablokowała z właściwego powodu, mówi
    dopiero uzasadnienie werdyktu — werdykt `block` na łamiącej wiadomości może stać na innej
    regule niż ta, którą sprawa łamie. Wydruk jest po to, żeby uzasadnienia przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `gate_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            GateReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, GateOutcome]] = []

    def record(
        self,
        graph:   str,          # np. "gate_reply"
        outcome: GateOutcome,  # np. judge_gate_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy bramki.

        Example args:
            graph="gate_reply"
            outcome=GateOutcome(case=GateCase(case_id="g01", …), answer="block", …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: bramki w kolejności zgłoszenia, dla każdej linię z licznikami, pod nią
        liczniki każdej reguły, a niżej sprawy z oceną, liczbą poprawek i polami werdyktu.
        Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["gate_reply: fałszywych alarmów 1 z 6, przepuszczeń 0 z 3, nie do przyjęcia 0",
             "    reguła 1: fałszywych alarmów 1 z 2, przepuszczeń 0 z 1, nie do przyjęcia 0",
             …,
             "    g01 reguła 1, łamie: zgodny; poprawek 0",
             "        verdict: block",
             …]
        """
        graphs = list(dict.fromkeys(graph for graph, _ in self._records))
        lines: list[str] = []

        for graph in graphs:
            outcomes = [outcome for name, outcome in self._records if name == graph]
            rules    = sorted({outcome.case.rule for outcome in outcomes})

            lines.append(f"{graph}: {_counts(outcomes)}")
            lines.extend(
                f"    reguła {rule}: "
                f"{_counts([outcome for outcome in outcomes if outcome.case.rule == rule])}"
                for rule in rules
            )

            for outcome in outcomes:
                lines.append(
                    f"    {outcome.case.label}: {outcome.assessment}; poprawek {outcome.retries}"
                )
                lines.extend(field_lines(outcome.fields))

        return lines


def _counts(
    outcomes: Sequence[GateOutcome],  # np. oceny spraw jednej reguły
) -> str:
    """
    Description:
    Liczniki do raportu: fałszywe alarmy wśród spraw, które mają przejść, przepuszczenia wśród
    tych, które mają zostać zablokowane, i odpowiedzi nie do przyjęcia.

    Example args:
        outcomes=[GateOutcome(case=GateCase(kind="breaks", …), answer="block", …), …]

    Example result:
        "fałszywych alarmów 1 z 2, przepuszczeń 0 z 1, nie do przyjęcia 0"
    """
    should_pass  = [outcome for outcome in outcomes if outcome.case.expected == "pass"]
    should_block = [outcome for outcome in outcomes if outcome.case.expected == "block"]

    false_alarms = sum(outcome.false_alarm for outcome in should_pass)
    misses       = sum(outcome.miss for outcome in should_block)
    rejected     = sum(outcome.rejected for outcome in outcomes)

    counts = (
        f"fałszywych alarmów {false_alarms} z {len(should_pass)}, "
        f"przepuszczeń {misses} z {len(should_block)}, "
        f"nie do przyjęcia {rejected}"
    )

    return counts
