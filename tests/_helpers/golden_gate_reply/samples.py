"""
Description:
Próbki do testów samego helpera zestawu bramki wysyłki
(`tests/unit/test_golden_gate_reply_report.py`, `tests/unit/test_golden_gate_reply_measure.py`):
wpis zestawu o podanych łamanych regułach, werdykty, ocena gotowa do raportu i stan końcowy
grafu. Dzięki nim plik testu to same testy, a dane, na których stoją asercje, leżą obok helpera,
którego dotyczą.

| co                  | do czego                                                 |
|---------------------|----------------------------------------------------------|
| `sample_case()`     | wpis zestawu o podanych łamanych regułach i warstwie     |
| `sample_block()`    | blokada z uzasadnieniem i wskazówką                      |
| `sample_pass()`     | przepuszczenie                                           |
| `sample_outcome()`  | ocena wpisu po podanym werdykcie, z czasem sprawy        |
| `sample_final()`    | stan końcowy grafu `gate_reply` z podanym werdyktem      |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `gate-reply.json`, który leży poza repo.
"""

from collections.abc import Sequence

from pydantic import BaseModel

from app.agent_graphs import gate_reply
from app.core_model.graphs.verdict import Verdict
from tests._helpers.golden_gate_reply.helper import judge_gate_reply_case
from tests._helpers.golden_gate_reply.models.gate_reply_outcome import GateReplyOutcome
from tests._helpers.golden_gate_reply.models.golden_gate_reply_case import GoldenGateReplyCase
from tests._helpers.golden_gate_reply.models.rule_violation import RuleViolation


def sample_case(
    rules:    Sequence[int] = (),        # np. (3, 5) — łamane reguły; pusta — wiadomość poprawna
    stratum:  str = "random",            # np. "keywords"
    doubtful: bool = False,              # np. True — przypadek graniczny
    ticket:   str = "90001",             # np. "90002"
    digest:   str = "0000000000000000",  # np. message_digest("wiadomość 90001")
) -> GoldenGateReplyCase:
    """
    Description:
    Buduje wpis zestawu o podanych łamanych regułach i warstwie, z powodami, po których raport
    rozpozna, którą regułę wypisał, i ze skrótem wiadomości, który podaje test pomiaru.

    Example args:
        rules=(5,)
        stratum="random"

    Example result:
        GoldenGateReplyCase(ticket_id="90001", comment=1, stratum="random",
                            digest="0000000000000000",
                            violations=(RuleViolation(rule=5, reason="Powód reguły 5."),),
                            doubtful=False, doubt=None)
    """
    case = GoldenGateReplyCase(
        ticket_id  = ticket,
        comment    = 1,
        stratum    = stratum,
        digest     = digest,
        violations = tuple(RuleViolation(rule=r, reason=f"Powód reguły {r}.") for r in rules),
        doubtful   = doubtful,
        doubt      = "Wątpliwość oceniającego." if doubtful else None,
    )

    return case


def sample_block() -> Verdict:
    """
    Description:
    Blokada z uzasadnieniem i wskazówką: werdykt, który raport wypisuje we wszystkich polach.

    Example args:
        (brak)

    Example result:
        Verdict(verdict="block", reasons=["Literówka „prosze”."], hint="Popraw pisownię.")
    """
    return Verdict(verdict="block", reasons=["Literówka „prosze”."], hint="Popraw pisownię.")


def sample_pass() -> Verdict:
    """
    Description:
    Przepuszczenie bez uzasadnienia.

    Example args:
        (brak)

    Example result:
        Verdict(verdict="pass")
    """
    return Verdict(verdict="pass")


def sample_outcome(
    case:    GoldenGateReplyCase,  # np. sample_case(rules=(5,))
    verdict: Verdict | None,       # np. sample_pass(); None — odpowiedź nie do przyjęcia
    seconds: float = 2.0,          # np. 4.5
) -> GateReplyOutcome:
    """
    Description:
    Ocenia wpis po podanym werdykcie tą samą funkcją co pomiar, bez poprawek odpowiedzi.

    Example args:
        case=sample_case(rules=(5,))
        verdict=sample_pass()
        seconds=2.0

    Example result:
        GateReplyOutcome(case=GoldenGateReplyCase(…), answer="pass", retries=0, …, seconds=2.0)
    """
    return judge_gate_reply_case(case=case, output=verdict, retries=0, seconds=seconds)


def sample_final(
    verdict: Verdict,  # np. sample_block()
) -> BaseModel:
    """
    Description:
    Stan końcowy grafu `gate_reply` po sprawie, której werdykt węzeł odpowiedzi przyjął bez
    poprawki: stan przykładowy grafu z podanym werdyktem. Tak wygląda wynik sprawy z
    `run_timed_live_cases()`, który pomiar ocenia.

    Example args:
        verdict=sample_block()

    Example result:
        GateReplyState(output=Verdict(verdict="block", …), respond_retries=0, …)
    """
    final = gate_reply.example_state().model_copy(update={"output": verdict, "respond_retries": 0})

    return final
