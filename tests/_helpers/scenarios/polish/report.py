"""
Description:
Raport scenariuszy „Popraw”: `PolishReport` zbiera oceny spraw z jednego przebiegu pytesta
i składa wydruk, który pytest pokazuje po testach — liczniki znalezisk, a pod nimi każdą
sprawę z oceną i poprawionym tekstem w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `polish_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy, więc zmiana wydruku pól dotyczy wszystkich czterech.
"""

from tests._helpers.scenarios.injections import field_lines
from tests._helpers.scenarios.polish.models.polish_outcome import PolishOutcome


class PolishReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy „Popraw” w jednym przebiegu pytesta i składa z nich
    wydruk: dla grafu linię z licznikami, a pod nią każdą sprawę z oceną i poprawionym tekstem
    w całości.

    Do czego:
    Test łapie słowa z list, a o tym, czy tekst nie dodał kroku albo obietnicy, której nie ma na
    żadnej liście, mówi dopiero sam tekst. Wydruk jest po to, żeby go przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `polish_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            PolishReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, PolishOutcome]] = []

    def record(
        self,
        graph:   str,            # np. "polish"
        outcome: PolishOutcome,  # np. judge_polish_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            graph="polish"
            outcome=PolishOutcome(case=PolishCase(case_id="s01", …), …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: grafy w kolejności zgłoszenia, dla każdego linię z licznikami, a pod nią
        sprawy z oceną, liczbą poprawek i poprawionym tekstem. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["polish: potoczne w 0 z 4, zgubione fakty w 0 z 4, nowe liczby w 0 z 4, "
             "dopisane w 0 z 4, nie do przyjęcia 0",
             "    s01 słowa potoczne i liczba w notatkach: zgodny; poprawek 0",
             "        text: Dzień dobry,",
             …]
        """
        graphs = list(dict.fromkeys(graph for graph, _ in self._records))
        lines: list[str] = []

        for graph in graphs:
            outcomes = [outcome for name, outcome in self._records if name == graph]
            total    = len(outcomes)

            lines.append(
                f"{graph}: "
                f"potoczne w {sum(bool(outcome.colloquial) for outcome in outcomes)} z {total}, "
                f"zgubione fakty w {sum(bool(outcome.lost) for outcome in outcomes)} z {total}, "
                f"nowe liczby w {sum(bool(outcome.new_numbers) for outcome in outcomes)} "
                f"z {total}, "
                f"dopisane w {sum(bool(outcome.added) for outcome in outcomes)} z {total}, "
                f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}"
            )

            for outcome in outcomes:
                lines.append(
                    f"    {outcome.case.label}: {outcome.assessment}; poprawek {outcome.retries}"
                )
                lines.extend(field_lines(outcome.fields))

        return lines
