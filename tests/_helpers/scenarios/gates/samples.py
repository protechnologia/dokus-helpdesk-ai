"""
Description:
Próbki do testów samego helpera bramek (`tests/unit/test_gate_report.py`): werdykty i sprawa
bramki danego rodzaju. Dzięki nim plik testu to same testy, a dane, na których stoją asercje,
leżą obok helpera, którego dotyczą.

| co            | do czego                                                       |
|---------------|----------------------------------------------------------------|
| `BLOCK`       | blokada z uzasadnieniem i wskazówką                            |
| `PASS`        | przepuszczenie                                                 |
| `gate_case()` | sprawa danego rodzaju przy danej regule                        |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `gates.json`: zestaw zmienia się
  z pomiarami, a próbki tylko razem z oceną.
"""

from app.core_model.graphs.verdict import Verdict
from tests._helpers.scenarios.gates.models.gate_case import GateCase

# Blokada z uzasadnieniem i wskazówką: werdykt, który raport wypisuje we wszystkich polach.
BLOCK = Verdict(verdict="block", reasons=["Prośba o hasło."], hint="Usuń prośbę o hasło.")

# Przepuszczenie: werdykt bez uzasadnienia.
PASS = Verdict(verdict="pass")


def gate_case(
    kind: str,      # np. "trap"
    rule: int = 1,  # np. 2
) -> GateCase:
    """
    Description:
    Buduje sprawę bramki danego rodzaju przy danej regule, z identyfikatorem złożonym z obu.

    Example args:
        kind="trap"
        rule=1

    Example result:
        GateCase(case_id="1-trap", rule=1, kind="trap", text="Dzień dobry, …")
    """
    case = GateCase(
        case_id = f"{rule}-{kind}",
        rule    = rule,
        kind    = kind,
        text    = "Dzień dobry, …",
    )

    return case
