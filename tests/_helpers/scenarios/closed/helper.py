"""
Description:
Zestaw scenariuszy trasy zamknięcia zgłoszenia (`data/safe/golden/closed.json`) i ocena odpowiedzi
trasy `POST /tickets/closed` na żywym modelu: czy zamknięcie skończyło się wynikiem, którego
sprawa wymaga — zablokowane przez bramkę, w indeksach albo odrzucone przez filtr. Korzysta z niego
test ewaluacyjny trasy (p. 30). Modele leżą w `models/`, raport w `report.py`, a przebieg spraw
przez trasę w `measure.py`.

| co                    | do czego                                    |
|-----------------------|---------------------------------------------|
| `closed_cases()`      | sprawy zestawu w jego kolejności            |
| `judge_closed_case()` | ocena odpowiedzi trasy na jedną sprawę      |

Oceny:

| sprawa wymaga        | trasa oddała             | ocena                      |
|----------------------|--------------------------|----------------------------|
| `indexed`, `dropped` | `blocked`                | ZABLOKOWANE BEZ POWODU     |
| `blocked`            | `indexed`, `dropped`     | PRZEPUSZCZONE PRZEZ BRAMKĘ |
| `indexed`            | `dropped` (i odwrotnie)  | FILTR ZDECYDOWAŁ INACZEJ   |
| dowolny              | kod inny niż 200         | BŁĄD TRASY                 |

Przykład — dobre zamknięcie zablokowane:

    outcome = judge_closed_case(
        case   = ClosedCase(case_id="c01", expected="indexed", request={…}),
        status = 200,
        body   = {"outcome": "blocked", "verdict": "block", "reasons": ["…"], …},
    )

    outcome.false_block -> True
    outcome.assessment  -> "ZABLOKOWANE BEZ POWODU"
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tests._helpers.scenarios.closed.constants import CLOSED_FILE
from tests._helpers.scenarios.closed.models.closed_case import ClosedCase
from tests._helpers.scenarios.closed.models.closed_outcome import ClosedOutcome

# Pola odpowiedzi trasy, które raport wypisuje przy sprawie: werdykt bramki i to, co filtr
# powiedział o karcie.
REPORTED_FIELDS = ("verdict", "reasons", "hint", "useful_reason", "dropped_by")


def closed_cases(
    path: Path = CLOSED_FILE,  # np. Path("data/safe/golden/closed.json")
) -> tuple[ClosedCase, ...]:
    """
    Description:
    Czyta zestaw scenariuszy trasy zamknięcia i oddaje jego sprawy w kolejności zestawu, bez
    metryczki.

    Example args:
        path=Path("data/safe/golden/closed.json")

    Example result:
        (ClosedCase(case_id="c01", expected="indexed", request={"ticket_id": "90601", …}), …)
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    cases = tuple(
        ClosedCase(
            case_id  = entry["id"],
            expected = entry["expected"],
            request  = entry["request"],
        )
        for entry in raw["cases"]
    )

    return cases


def judge_closed_case(
    case:   ClosedCase,         # np. ClosedCase(case_id="c01", expected="indexed", …)
    status: int,                # np. 200
    body:   Mapping[str, Any],  # treść odpowiedzi, np. {"outcome": "indexed", …}
) -> ClosedOutcome:
    """
    Description:
    Ocenia odpowiedź trasy na jedną sprawę: zapisuje wynik i pola do raportu, a kod inny niż 200
    jako brak wyniku. Czy bramka albo filtr zdecydowały źle, mówi ocena.

    Example args:
        case=ClosedCase(case_id="c03", expected="blocked", request={…})
        status=200
        body={"outcome": "indexed", "verdict": "pass", "useful_reason": "…", …}

    Example result:
        ClosedOutcome(case=ClosedCase(case_id="c03", …), status=200, answer="indexed",
                      fields={"verdict": "pass", …})
    """
    # --- trasa nie oddała wyniku: w odpowiedzi stoi sam błąd ---
    if status != 200:
        failed = ClosedOutcome(
            case   = case,
            status = status,
            answer = None,
            fields = dict(body),
        )

        return failed

    outcome = ClosedOutcome(
        case   = case,
        status = status,
        answer = body["outcome"],
        fields = {name: body[name] for name in REPORTED_FIELDS},
    )

    return outcome
