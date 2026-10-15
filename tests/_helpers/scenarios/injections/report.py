"""
Description:
Raport scenariuszy wstrzyknięć: `InjectionReport` zbiera oceny spraw z jednego przebiegu
pytesta i składa wydruk, który pytest pokazuje po testach — dla każdego grafu liczbę
przebić, a pod nią każdą sprawę z oceną i polami wyniku w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `injection_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy, więc zmiana wydruku pól dotyczy wszystkich czterech.
"""

from tests._helpers.scenarios.injections.helper import field_lines
from tests._helpers.scenarios.injections.models.injection_outcome import InjectionOutcome


class InjectionReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy wstrzyknięć w jednym przebiegu pytesta i składa z nich
    wydruk: dla każdego grafu linię z liczbą przebić, pod nią każdą sprawę z oceną i polami
    wyniku w całości.

    Do czego:
    Test zalicza zestaw po znacznikach i werdykcie, ale o tym, czy model naprawdę odparł atak,
    mówią dopiero surowe odpowiedzi — znacznik może brakować w tekście, który mimo to spełnia
    polecenie z ataku. Wydruk jest po to, żeby te odpowiedzi przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `injection_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            InjectionReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, InjectionOutcome]] = []

    def record(
        self,
        graph:   str,               # np. "suggest_handoff"
        outcome: InjectionOutcome,  # np. judge_run(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy grafu.

        Example args:
            graph="suggest_handoff"
            outcome=InjectionOutcome(label="h01 …", control=False, …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: grafy w kolejności zgłoszenia, dla każdego linię z liczbą przebić wśród
        ataków, a pod nią sprawy z oceną, liczbą poprawek i polami wyniku. Tekst wielolinijkowy
        stoi pod nazwą pola, z wcięciem. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["suggest_handoff: przebitych 0 z 6 ataków, niedotartych do modelu 0",
             "    kontrolna podpis: bez znaczników; poprawek 0",
             "        text: Dzień dobry,",
             "              przekazujemy sprawę…",
             "        internal_notes: ",
             "    h01 polecenie wprost w komentarzu klienta: odparty; poprawek 0",
             …]
        """
        graphs = list(dict.fromkeys(graph for graph, _ in self._records))
        lines: list[str] = []

        for graph in graphs:
            outcomes = [outcome for name, outcome in self._records if name == graph]
            attacks  = [outcome for outcome in outcomes if not outcome.control]
            breached = sum(outcome.breached for outcome in attacks)
            missed   = sum(not outcome.delivered for outcome in attacks)

            lines.append(
                f"{graph}: przebitych {breached} z {len(attacks)} ataków, "
                f"niedotartych do modelu {missed}"
            )

            for outcome in outcomes:
                lines.append(f"    {outcome.label}: {outcome.verdict}; poprawek {outcome.retries}")
                lines.extend(field_lines(outcome.fields))

        return lines
