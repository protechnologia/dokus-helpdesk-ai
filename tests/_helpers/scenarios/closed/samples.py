"""
Description:
Próbki do testów samego helpera scenariuszy trasy zamknięcia (`tests/unit/test_closed_report.py`):
sprawa wymagająca danego wyniku i odpowiedź trasy z danym wynikiem. Dzięki nim plik testu to same
testy, a dane, na których stoją asercje, leżą obok helpera.

| co                  | do czego                                          |
|---------------------|---------------------------------------------------|
| `sample_case()`     | sprawa wymagająca podanego wyniku                 |
| `sample_answer()`   | odpowiedź trasy z podanym wynikiem i werdyktem    |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `closed.json`.
"""

from typing import Any

from tests._helpers.scenarios.closed.models.closed_case import ClosedCase


def sample_case(
    expected: str,  # np. "indexed"
) -> ClosedCase:
    """
    Description:
    Zwraca sprawę wymagającą podanego wyniku, z identyfikatorem od tego wyniku.

    Example args:
        expected="indexed"

    Example result:
        ClosedCase(case_id="indexed", expected="indexed", request={"ticket_id": "90001", …})
    """
    case = ClosedCase(
        case_id  = expected,
        expected = expected,
        request  = {"ticket_id": "90001", "body": "Nie przychodzą przesyłki."},
    )

    return case


def sample_answer(
    outcome: str,  # np. "blocked"
) -> dict[str, Any]:
    """
    Description:
    Zwraca odpowiedź trasy z podanym wynikiem: przy blokadzie werdykt `block` z powodem, przy
    karcie werdykt `pass` z uzasadnieniem karty, a przy odrzuceniu także regułę filtra.

    Example args:
        outcome="dropped"

    Example result:
        {"outcome": "dropped", "verdict": "pass", "useful_reason": "Tylko termin.",
         "dropped_by": [{"rule": "not_useful", "evidence": "Tylko termin."}], …}
    """
    blocked = outcome == "blocked"
    reason  = None if blocked else "Tylko termin."
    hits    = [{"rule": "not_useful", "evidence": reason}] if outcome == "dropped" else []
    usage   = {
        "llm_calls":          1,
        "prompt_tokens":      0,
        "completion_tokens":  0,
        "cache_write_tokens": 0,
        "cache_read_tokens":  0,
        "cost_usd":           0.0,
    }

    answer = {
        "ticket_id":     "90001",
        "outcome":       outcome,
        "replaced":      False,
        "verdict":       "block" if blocked else "pass",
        "reasons":       ["Nie widać, co zrobiono."] if blocked else [],
        "hint":          "Dopisz, co zrobiono." if blocked else "",
        "overridable":   True,
        "rules_version": 1,
        "useful_reason": reason,
        "dropped_by":    hits,
        "usage":         usage,
        "log":           [],
    }

    return answer
