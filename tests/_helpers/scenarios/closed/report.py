"""
Description:
Raport scenariuszy trasy zamknięcia zgłoszenia: `ClosedReport` zbiera oceny spraw z jednego
przebiegu pytesta i składa wydruk, który pytest pokazuje po testach — liczniki błędów bramki,
filtra i trasy, a niżej każdą sprawę z oceną i polami odpowiedzi w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `closed_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola odpowiedzi wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy.
"""

from tests._helpers.scenarios.closed.models.closed_outcome import ClosedOutcome
from tests._helpers.scenarios.injections import field_lines


class ClosedReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy trasy zamknięcia w jednym przebiegu pytesta i składa z nich
    wydruk: linię z licznikami, a niżej każdą sprawę z oceną, kodem odpowiedzi i jej polami.

    Do czego:
    Test zalicza zestaw po samym wyniku, ale dlaczego bramka zablokowała albo filtr odrzucił
    kartę, mówią dopiero uzasadnienie werdyktu i `useful_reason` karty. Wydruk jest po to, żeby
    je przeczytać.

    Flow:
        1. Pomiar dostaje raport przez fixture `closed_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            ClosedReport bez zgłoszonych spraw
        """
        self._outcomes: list[ClosedOutcome] = []

    def record(
        self,
        outcome: ClosedOutcome,  # np. judge_closed_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            outcome=ClosedOutcome(case=ClosedCase(case_id="c01", …), status=200, …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._outcomes.append(outcome)

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: linię z licznikami, a niżej sprawy w kolejności zgłoszenia, z oceną, kodem
        odpowiedzi i polami. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["/tickets/closed: zgodnych 5 z 6, zablokowanych bez powodu 1, przepuszczonych przez "
             "bramkę 0, filtr inaczej 0, błędów trasy 0",
             "    c01 do indeksów: ZABLOKOWANE BEZ POWODU; kod 200",
             "        verdict: block",
             …]
        """
        if not self._outcomes:
            return []

        outcomes = self._outcomes
        agreed   = sum(outcome.assessment == "zgodny" for outcome in outcomes)

        lines = [
            f"/tickets/closed: zgodnych {agreed} z {len(outcomes)}, "
            f"zablokowanych bez powodu {sum(outcome.false_block for outcome in outcomes)}, "
            f"przepuszczonych przez bramkę {sum(outcome.missed_block for outcome in outcomes)}, "
            f"filtr inaczej {sum(outcome.wrong_filter for outcome in outcomes)}, "
            f"błędów trasy {sum(outcome.failed for outcome in outcomes)}",
        ]

        for outcome in outcomes:
            lines.append(f"    {outcome.case.label}: {outcome.assessment}; kod {outcome.status}")
            lines.extend(field_lines(outcome.fields))

        return lines
