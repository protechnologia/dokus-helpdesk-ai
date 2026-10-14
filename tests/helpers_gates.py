"""
Description:
Zestaw scenariuszy bramek (`data/safe/golden/gates.json`) i ocena sprawy przeprowadzonej na żywym
modelu: czy bramka wydała werdykt, którego wejście wymaga. Na każdą regułę klienta zestaw ma trzy
wejścia: łamiące ją, poprawnego bliźniaka i pułapkę — poprawne, które wygląda na łamiące.
Korzysta z niego test ewaluacyjny bramek (p. 59), a raport stąd pytest wypisuje po przebiegu.

| co                  | do czego                                                       |
|---------------------|----------------------------------------------------------------|
| `gate_sections()`   | sekcje zestawu po nazwie bramki                                |
| `GateSection`       | sekcja jednej bramki: wersja reguł i sprawy                    |
| `GateCase`          | jedno wejście: reguła, rodzaj i oczekiwany werdykt             |
| `judge_gate_case()` | ocena jednej sprawy                                            |
| `GateOutcome`       | wynik oceny: zgodny, fałszywy alarm, przepuszczenie albo brak werdyktu |
| `GateReport`        | raport: `record()` dopisuje sprawę, `lines()` składa wydruk    |

Rodzaje spraw:

| rodzaj    | w raporcie | oczekiwany werdykt | zły werdykt to   |
|-----------|------------|--------------------|------------------|
| `breaks`  | łamie      | `block`            | przepuszczenie   |
| `correct` | poprawna   | `pass`             | fałszywy alarm   |
| `trap`    | pułapka    | `pass`             | fałszywy alarm   |

Przykład — pułapka zablokowana:

    outcome = judge_gate_case(
        case    = GateCase(case_id="g03", rule=1, kind="trap", text="Dzień dobry, hasło…"),
        output  = Verdict(verdict="block", reasons=["Wiadomość wspomina hasło."], hint="…"),
        retries = 0,
    )

    outcome.false_alarm -> True
    outcome.assessment  -> "FAŁSZYWY ALARM"

O czym pamiętać przy zmianach:

- Reguły bierze się z zestawu domyślnego bramki, tak jak trasa; sekcja zapisuje jego wersję,
  a numer reguły przy sprawie liczy się od 1, w kolejności zestawu.
- Odpowiedź nie do przyjęcia nie jest ani fałszywym alarmem, ani przepuszczeniem: helpdesk
  dostaje wtedy 503 i decyduje sam. Liczy się osobno.
- Raport dostaje się przez fixture `gate_report` z `tests/conftest.py`, jeden na cały przebieg;
  tam też stoi funkcja, która go wypisuje.
"""

import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tests.helpers_injections import field_lines

GATES_FILE = Path("data/safe/golden/gates.json")

# Klucz zestawu z metryczką, a nie sekcja bramki.
META_KEY = "meta"

# Werdykt, którego wymaga każdy rodzaj sprawy.
EXPECTED_VERDICTS = {"breaks": "block", "correct": "pass", "trap": "pass"}

# Rodzaj sprawy w raporcie.
KIND_LABELS = {"breaks": "łamie", "correct": "poprawna", "trap": "pułapka"}


@dataclasses.dataclass(frozen=True)
class GateCase:
    """Jedno wejście bramki z zestawu: reguła, której dotyczy, i rodzaj sprawy."""

    case_id: str  # np. "g01"
    rule:    int  # np. 1 — numer reguły w zestawie domyślnym, od 1
    kind:    str  # np. "breaks"; także "correct" albo "trap"
    text:    str  # wejście bramki, np. "Dzień dobry,\n\nprosimy Państwa o przesłanie…"

    @property
    def expected(self) -> str:
        """
        Description:
        Werdykt, którego wymaga rodzaj sprawy.

        Example args:
            (brak)

        Example result:
            "block"
        """
        return EXPECTED_VERDICTS[self.kind]

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator, reguła i rodzaj.

        Example args:
            (brak)

        Example result:
            "g01 reguła 1, łamie"
        """
        return f"{self.case_id} reguła {self.rule}, {KIND_LABELS[self.kind]}"


@dataclasses.dataclass(frozen=True)
class GateSection:
    """Sekcja zestawu dla jednej bramki: wersja reguł, pod którą napisano sprawy, i sprawy."""

    graph:         str                    # np. "gate_reply"
    rules_version: int                    # np. 1 — wersja zestawu domyślnego reguł bramki
    cases:         tuple[GateCase, ...]   # sprawy w kolejności zestawu


@dataclasses.dataclass(frozen=True)
class GateOutcome:
    """Ocena jednej sprawy bramki."""

    case:    GateCase           # sprawa, której dotyczy ocena
    answer:  str | None         # werdykt bramki, np. "block"; None — odpowiedź nie do przyjęcia
    retries: int                # poprawki odpowiedzi od węzła `respond`
    fields:  Mapping[str, Any]  # pola werdyktu do raportu; puste, gdy werdyktu nie ma

    @property
    def rejected(self) -> bool:
        """
        Description:
        Czy węzeł `respond` nie przyjął odpowiedzi mimo poprawki.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.answer is None

    @property
    def false_alarm(self) -> bool:
        """
        Description:
        Czy bramka zablokowała wejście, które reguły nie łamie: poprawne albo pułapkę.

        Example args:
            (brak)

        Example result:
            True
        """
        return self.answer == "block" and self.case.expected == "pass"

    @property
    def miss(self) -> bool:
        """
        Description:
        Czy bramka przepuściła wejście, które łamie regułę.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.answer == "pass" and self.case.expected == "block"

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym słowem albo dwoma dla raportu.

        Example args:
            (brak)

        Example result:
            "FAŁSZYWY ALARM"
        """
        # --- odpowiedź nie do przyjęcia: werdyktu nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        # --- poprawne wejście zablokowane ---
        if self.false_alarm:
            return "FAŁSZYWY ALARM"

        # --- łamiące wejście przepuszczone ---
        if self.miss:
            return "PRZEPUSZCZENIE"

        return "zgodny"


def gate_sections(
    path: Path = GATES_FILE,  # np. Path("data/safe/golden/gates.json")
) -> dict[str, GateSection]:
    """
    Description:
    Czyta zestaw scenariuszy bramek i oddaje jego sekcje po nazwie bramki, bez metryczki.

    Example args:
        path=Path("data/safe/golden/gates.json")

    Example result:
        {"gate_reply": GateSection(graph="gate_reply", rules_version=1,
                                   cases=(GateCase(case_id="g01", rule=1, kind="breaks", …), …))}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    sections = {
        graph: GateSection(
            graph         = graph,
            rules_version = body["rules_version"],
            cases         = tuple(_case_from(entry) for entry in body["cases"]),
        )
        for graph, body in raw.items()
        if graph != META_KEY
    }

    return sections


def _case_from(
    entry: Mapping[str, Any],  # np. {"id": "g01", "rule": 1, "kind": "breaks", "input": "…"}
) -> GateCase:
    """
    Description:
    Zamienia wpis sprawy z zestawu na `GateCase`; nazwy pól zestawu są krótsze.

    Example args:
        entry={"id": "g01", "rule": 1, "kind": "breaks", "input": "Dzień dobry, …"}

    Example result:
        GateCase(case_id="g01", rule=1, kind="breaks", text="Dzień dobry, …")
    """
    case = GateCase(
        case_id = entry["id"],
        rule    = entry["rule"],
        kind    = entry["kind"],
        text    = entry["input"],
    )

    return case


def judge_gate_case(
    case:    GateCase,          # np. GateCase(case_id="g03", rule=1, kind="trap", …)
    output:  BaseModel | None,  # np. Verdict(verdict="block", …); None — `respond` nie przyjął
    retries: int,               # np. 0 — poprawki odpowiedzi od węzła `respond`
) -> GateOutcome:
    """
    Description:
    Ocenia jedną sprawę bramki: zapisuje werdykt i pola wyniku do raportu, a brak wyniku jako
    odpowiedź nie do przyjęcia. Czy to fałszywy alarm, czy przepuszczenie, mówi ocena.

    Example args:
        case=GateCase(case_id="g03", rule=1, kind="trap", text="Dzień dobry, hasło…")
        output=Verdict(verdict="block", reasons=["Wiadomość wspomina hasło."], hint="…")
        retries=0

    Example result:
        GateOutcome(case=GateCase(case_id="g03", …), answer="block", retries=0,
                    fields={"verdict": "block", "reasons": […], "missing": [], "hint": "…"})
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = GateOutcome(
            case    = case,
            answer  = None,
            retries = retries,
            fields  = {},
        )

        return rejected

    fields = output.model_dump(mode="json")

    outcome = GateOutcome(
        case    = case,
        answer  = fields["verdict"],
        retries = retries,
        fields  = fields,
    )

    return outcome


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
