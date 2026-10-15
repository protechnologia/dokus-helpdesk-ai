import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.injections.models.injection_attack import InjectionAttack


@dataclasses.dataclass(frozen=True)
class InjectionSection:
    """Sekcja zestawu dla jednego grafu: pola chronione, oczekiwane pola wyniku, wejścia bez
    ataku i ataki."""

    graph:          str                          # np. "suggest_handoff"
    guarded_fields: tuple[str, ...]              # np. ("text",); w bramce puste
    inputs:         Mapping[str, str]            # np. {"podpis": "ZGŁOSZENIE 90101…"}
    attacks:        tuple[InjectionAttack, ...]  # ataki w kolejności zestawu
    rules_version:  int | None = None            # np. 1 — wersja zestawu domyślnego reguł klienta

    # Pola wyniku, których wejście wymaga z atakiem i bez, np. {"haslo": {"verdict": "block"}}.
    expected: Mapping[str, Mapping[str, Any]] = dataclasses.field(default_factory=dict)

    def markers_on(
        self,
        input_id: str,  # np. "podpis"
    ) -> tuple[str, ...]:
        """
        Description:
        Znaczniki wszystkich ataków doklejanych do tego wejścia — tych szuka się w wyniku
        sprawy kontrolnej.

        Example args:
            input_id="podpis"

        Example result:
            ("KANAREK-4417", "logowanie-7731", "SERVICE-OK-2210")
        """
        markers = tuple(
            marker
            for attack in self.attacks
            if attack.input_id == input_id
            for marker in attack.markers
        )

        return markers
