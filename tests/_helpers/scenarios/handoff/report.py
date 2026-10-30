"""
Description:
Raport scenariuszy przekazania sprawy: `HandoffReport` zbiera oceny spraw z jednego przebiegu
pytesta i składa wydruk, który pytest pokazuje po testach — liczniki znalezisk, a pod nimi każdą
sprawę z oceną i wiadomością w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `handoff_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów scenariuszy.
"""

from tests._helpers.scenarios.handoff.models.handoff_outcome import HandoffOutcome
from tests._helpers.scenarios.injections import field_lines


class HandoffReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy przekazania w jednym przebiegu pytesta i składa z nich
    wydruk: dla grafu linię z licznikami, a pod nią każdą sprawę z oceną i wiadomością w całości.

    Do czego:
    Test łapie słowa z list, a o tym, czy wiadomość nie podała przypuszczenia jako ustalenia, mówi
    dopiero sama wiadomość. Wydruk jest po to, żeby go przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `handoff_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            HandoffReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, HandoffOutcome]] = []

    def record(
        self,
        graph:   str,             # np. "suggest_handoff"
        outcome: HandoffOutcome,  # np. judge_handoff_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            graph="suggest_handoff"
            outcome=HandoffOutcome(case=HandoffCase(case_id="h01", …), …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: grafy w kolejności zgłoszenia, dla każdego linię z licznikami, a pod nią
        sprawy z oceną, liczbą poprawek i wiadomością. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["suggest_handoff: układ inny w 0 z 8, zgubione fakty w 0 z 8, zgubione ostrzeżenia "
             "w 0 z 8, dopisane w 0 z 8, obietnice w 0 z 8, z przykładu w 0 z 8, "
             "nie do przyjęcia 0",
             "    h01 inny temat niż w przykładzie…: zgodny; poprawek 0",
             "        text: Dzień dobry.",
             …]
        """
        graphs = list(dict.fromkeys(graph for graph, _ in self._records))
        lines: list[str] = []

        for graph in graphs:
            outcomes = [outcome for name, outcome in self._records if name == graph]
            total    = len(outcomes)

            added = sum(bool(outcome.new_numbers or outcome.added) for outcome in outcomes)

            lines.append(
                f"{graph}: "
                f"układ inny w {sum(bool(outcome.layout) for outcome in outcomes)} z {total}, "
                f"zgubione fakty w {sum(bool(outcome.lost) for outcome in outcomes)} z {total}, "
                f"zgubione ostrzeżenia w {sum(outcome.warning_lost for outcome in outcomes)} "
                f"z {total}, "
                f"dopisane w {added} z {total}, "
                f"obietnice w {sum(bool(outcome.promised) for outcome in outcomes)} z {total}, "
                f"z przykładu w {sum(bool(outcome.copied) for outcome in outcomes)} z {total}, "
                f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}"
            )

            for outcome in outcomes:
                lines.append(
                    f"    {outcome.case.label}: {outcome.assessment}; poprawek {outcome.retries}"
                )
                lines.extend(field_lines(outcome.fields))

        return lines
