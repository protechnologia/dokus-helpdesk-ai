import dataclasses

from tests._helpers.scenarios.gates.models.gate_case import GateCase


@dataclasses.dataclass(frozen=True)
class GateSection:
    """Sekcja zestawu dla jednej bramki: wersja reguł, pod którą napisano sprawy, i sprawy."""

    graph:         str                    # np. "gate_reply"
    rules_version: int                    # np. 1 — wersja zestawu domyślnego reguł bramki
    cases:         tuple[GateCase, ...]   # sprawy w kolejności zestawu
