"""
Description:
Węzeł `replace_found`, ostatni w grafie anonimizacji: z miejsc osób i adresów, które wskazały
węzły z modelem, wybiera te, które na siebie nie zachodzą, i zamienia je na znaczniki w tekście
po wzorcach.

Przykład (zmyślony; adres niesie ulicę nazwaną od osoby, którą węzeł osób wziął za nazwisko):

    tekst:   „Decyzja trafiła na Kościuszki 8/2, Tarnów.”
    miejsca: ADRES „Kościuszki 8/2, Tarnów”, NAZWISKO „Kościuszki”
    po:      „Decyzja trafiła na {ADRES}.”

O czym pamiętać przy zmianach:

- Dłuższe miejsce wygrywa, a przy równej długości adres (`ADDRESS_PRIORITY`): słowo z ulicy
  nazwanej od osoby węzeł osób bierze za nazwisko, a cały adres i tak ma zniknąć.
"""

from typing import Any

from pydantic import BaseModel

from anonymizer_app.agent_nodes.base import Node
from anonymizer_app.core_service.replacer_found import choose_found, replace_found

# Priorytet przy remisie długości dwóch miejsc: mniejszy wygrywa.
ADDRESS_PRIORITY = 0
PERSON_PRIORITY  = 1


class ReplaceFoundNode(Node):
    """
    Description:
    Węzeł grafu, który zamienia miejsca osób i adresów na znaczniki; przebieg opisuje docstring
    modułu. Rusza dopiero po obu węzłach z modelem.
    """

    name = "replace_found"

    async def run(
        self,
        state: BaseModel,  # np. AnonymizeState(after_patterns="…", persons=[…], addresses=[…])
    ) -> dict[str, Any]:
        """
        Description:
        Zapisuje w `output` tekst po wzorcach z miejscami osób i adresów zamienionymi na
        znaczniki; w logu ile miejsc wybrano z ilu.

        Example args:
            state=AnonymizeState(after_patterns="Decyzja trafiła na Kościuszki 8/2, Tarnów.",
                                 addresses=[Found(kind="ADRES", start=19, end=41)],
                                 persons=[Found(kind="NAZWISKO", start=19, end=29)])

        Example result:
            {"output": "Decyzja trafiła na {ADRES}.",
             "log": [LogEntry(node="replace_found", message="wybrane 1 z 2 miejsc")]}
        """
        candidates = (
            [(found, ADDRESS_PRIORITY) for found in state.addresses]
            + [(found, PERSON_PRIORITY) for found in state.persons]
        )
        chosen = choose_found(candidates)

        update = {
            "output": replace_found(state.after_patterns, chosen),
            "log":    [self.log_entry(f"wybrane {len(chosen)} z {len(candidates)} miejsc")],
        }

        return update
