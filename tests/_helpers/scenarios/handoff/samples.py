"""
Description:
Próbki do testów samego helpera przekazania (`tests/unit/test_handoff_report.py`): sprawa z listami
faktów, ostrzeżenia i pułapek oraz wiadomość, która żadnej z list nie łamie. Dzięki nim plik testu
to same testy, a dane, na których stoją asercje, leżą obok helpera, którego dotyczą.

| co                 | do czego                                                          |
|--------------------|-------------------------------------------------------------------|
| `sample_case()`    | zgłoszenie z dwoma faktami, ostrzeżeniem i jedną pułapką          |
| `sample_clean()`   | wiadomość w układzie z przykładu, z faktami i ostrzeżeniem        |
| `sample_judged()`  | ocena podanej wiadomości na sprawie z `sample_case()`             |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `handoff.json`: zestaw zmienia się
  z pomiarami, a próbki tylko razem z oceną.
"""

from app.core_model.graphs.proposal import Proposal
from tests._helpers.scenarios.handoff.helper import judge_handoff_case
from tests._helpers.scenarios.handoff.models.handoff_case import HandoffCase
from tests._helpers.scenarios.handoff.models.handoff_outcome import HandoffOutcome


def sample_case() -> HandoffCase:
    """
    Description:
    Sprawa z dwoma faktami, dwoma rdzeniami ostrzeżenia i pułapką: zgadywaną przyczyną, której
    w zgłoszeniu nie ma.

    Example args:
        (brak)

    Example result:
        HandoffCase(case_id="h04", text="ZGŁOSZENIE 90304 z 2026-10-30…", kept=("ePUAP", "12"), …)
    """
    case = HandoffCase(
        case_id    = "h04",
        phenomenon = "ostrzeżenie w wątku",
        text       = "ZGŁOSZENIE 90304 z 2026-10-30\nBłąd przy wysyłce 12 pism przez ePUAP.",
        kept       = ("ePUAP", "12"),
        warning    = ("nie ponawia", "wstrzyma"),
        tempting   = ("wygas",),
    )

    return case


def sample_clean() -> str:
    """
    Description:
    Wiadomość do sprawy z `sample_case()` zgodna ze wszystkimi listami, w układzie z przykładu.

    Example args:
        (brak)

    Example result:
        "Dzień dobry.\\n\\nPrzy wysyłce 12 pism przez ePUAP…\\n\\nPozdrawiam."
    """
    text = (
        "Dzień dobry.\n\n"
        "Przy wysyłce 12 pism przez ePUAP pojawił się błąd. Prosimy nie ponawiać wysyłki.\n\n"
        "Sprawę przekazujemy do dalszych prac po stronie serwisu.\n\n"
        "Pozdrawiam."
    )

    return text


def sample_judged(
    text: str,  # np. "Dzień dobry.\n\nPrzy wysyłce 12 pism…\n\nPozdrawiam."
) -> HandoffOutcome:
    """
    Description:
    Ocenia wiadomość o podanej treści na sprawie z `sample_case()`.

    Example args:
        text="Dzień dobry.\\n\\nPrzy wysyłce 12 pism…\\n\\nPozdrawiam."

    Example result:
        HandoffOutcome(case=HandoffCase(case_id="h04", …), layout=(), …)
    """
    outcome = judge_handoff_case(sample_case(), Proposal(text=text, internal_notes=""), retries=0)

    return outcome
