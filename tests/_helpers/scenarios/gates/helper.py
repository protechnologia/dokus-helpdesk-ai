"""
Description:
Zestaw scenariuszy bramek (`data/safe/golden/gates.json`) i ocena sprawy przeprowadzonej na żywym
modelu: czy bramka wydała werdykt, którego wejście wymaga. Na każdą regułę klienta zestaw ma trzy
wejścia: łamiące ją, poprawnego bliźniaka i pułapkę — poprawne, które wygląda na łamiące.
Korzysta z niego test ewaluacyjny bramek (p. 59). Modele zestawu i oceny leżą w `models/`,
a raport, który pytest wypisuje po przebiegu, w `report.py`.

| co                  | do czego                                                       |
|---------------------|----------------------------------------------------------------|
| `gate_sections()`   | sekcje zestawu po nazwie bramki                                |
| `judge_gate_case()` | ocena jednej sprawy                                            |

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
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tests._helpers.scenarios.gates.constants import GATES_FILE, META_KEY
from tests._helpers.scenarios.gates.models.gate_case import GateCase
from tests._helpers.scenarios.gates.models.gate_outcome import GateOutcome
from tests._helpers.scenarios.gates.models.gate_section import GateSection


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
                    fields={"verdict": "block", "reasons": […], "hint": "…"})
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
