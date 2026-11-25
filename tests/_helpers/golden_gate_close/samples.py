"""
Description:
Próbki do testów samego helpera zestawu bramki zamknięcia
(`tests/unit/test_golden_gate_close_report.py`, `tests/unit/test_golden_gate_close_measure.py`):
wpis zestawu o podanych etykietach, werdykty, ocena gotowa do raportu i stan końcowy grafu.
Dzięki nim plik testu to same testy, a dane, na których stoją asercje, leżą obok helpera, którego
dotyczą.

| co                  | do czego                                                 |
|---------------------|----------------------------------------------------------|
| `sample_case()`     | wpis zestawu o podanym rodzaju, etykietach i warstwie    |
| `sample_block()`    | blokada z uzasadnieniem i wskazówką                      |
| `sample_pass()`     | przepuszczenie                                           |
| `sample_outcome()`  | ocena wpisu po podanym werdykcie, z czasem sprawy        |
| `sample_final()`    | stan końcowy grafu `gate_close` z podanym werdyktem      |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `gate-close.json`, który leży poza repo.
"""

from pydantic import BaseModel

from app.agent_graphs import gate_close
from app.core_model.graphs.verdict import Verdict
from tests._helpers.golden_gate_close.helper import judge_gate_close_case
from tests._helpers.golden_gate_close.models.gate_close_outcome import GateCloseOutcome
from tests._helpers.golden_gate_close.models.golden_gate_close_case import GoldenGateCloseCase


def sample_case(
    kind:     str = "sprawa",            # np. "powiadomienie"
    problem:  bool = True,               # np. False — nie widać problemu
    action:   bool = True,               # np. False — nie widać rozwiązania
    stratum:  str = "random",            # np. "mail"
    doubtful: bool = False,              # np. True — przypadek graniczny
    ticket:   str = "90001",             # np. "90002"
    digest:   str = "0000000000000000",  # np. thread_digest("wątek 90001")
) -> GoldenGateCloseCase:
    """
    Description:
    Buduje wpis zestawu o podanym rodzaju, etykietach i warstwie, z powodami, po których raport
    rozpozna, którą etykietę wypisał, i ze skrótem wątku, który podaje test pomiaru.

    Example args:
        kind="sprawa"
        problem=True
        action=False

    Example result:
        GoldenGateCloseCase(ticket_id="90001", stratum="random", comments_at_close=2,
                            digest="0000000000000000", kind="sprawa", problem_visible=True,
                            problem_reason="Powód reguły 1.", action_visible=False,
                            action_reason="Powód reguły 2.", doubtful=False)
    """
    case = GoldenGateCloseCase(
        ticket_id         = ticket,
        stratum           = stratum,
        comments_at_close = 2,
        digest            = digest,
        kind              = kind,
        problem_visible   = problem,
        problem_reason    = "Powód reguły 1.",
        action_visible    = action,
        action_reason     = "Powód reguły 2.",
        doubtful          = doubtful,
    )

    return case


def sample_block() -> Verdict:
    """
    Description:
    Blokada z uzasadnieniem i wskazówką: werdykt, który raport wypisuje we wszystkich polach.

    Example args:
        (brak)

    Example result:
        Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz rozwiązanie.")
    """
    return Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz rozwiązanie.")


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
    case:    GoldenGateCloseCase,  # np. sample_case(action=False)
    verdict: Verdict | None,       # np. sample_pass(); None — odpowiedź nie do przyjęcia
    seconds: float = 3.0,          # np. 9.8
) -> GateCloseOutcome:
    """
    Description:
    Ocenia wpis po podanym werdykcie tą samą funkcją co pomiar, bez poprawek odpowiedzi.

    Example args:
        case=sample_case(action=False)
        verdict=sample_pass()
        seconds=3.0

    Example result:
        GateCloseOutcome(case=GoldenGateCloseCase(…), answer="pass", retries=0, …, seconds=3.0)
    """
    return judge_gate_close_case(case=case, output=verdict, retries=0, seconds=seconds)


def sample_final(
    verdict: Verdict,  # np. sample_block()
) -> BaseModel:
    """
    Description:
    Stan końcowy grafu `gate_close` po sprawie, której werdykt węzeł odpowiedzi przyjął bez
    poprawki: stan przykładowy grafu z podanym werdyktem. Tak wygląda wynik sprawy z
    `run_timed_live_cases()`, który pomiar ocenia.

    Example args:
        verdict=sample_block()

    Example result:
        GateCloseState(output=Verdict(verdict="block", …), respond_retries=0, …)
    """
    final = gate_close.example_state().model_copy(update={"output": verdict, "respond_retries": 0})

    return final
