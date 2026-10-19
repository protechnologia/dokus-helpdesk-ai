"""
Description:
Węzeł `split_chunks`: dzieli tekst po wzorcach na części, które model przejrzy osobno
(`split_into_chunks()`). Zwykłe zgłoszenie to jedna część; dzielą się tylko nieliczne długie
wątki. Model w każdej części tylko wskazuje fragmenty, a kolejne węzły szukają ich w całym
tekście, więc podział niczego nie gubi.

O czym pamiętać przy zmianach:

- `CHUNK_CHARS` razem z promptem i odpowiedzią musi mieścić się w oknie serwera modelu; pilnuje
  tego fabryka silnika przy starcie (`LLM_ANONYMIZATION_NUM_CTX`).
"""

from typing import Any

from pydantic import BaseModel

from anonymizer_app.agent_nodes.base import Node
from anonymizer_app.core_util.chunks import split_into_chunks

# Największa część tekstu dla jednego wywołania modelu, w znakach. Mediana wątku korpusu to 337
# tokenów, czyli około 700 znaków, a 99% wątków ma do 2827 tokenów (zmierzone 2026-10-19 na 1825
# zgłoszeniach), więc dzielą się tylko nieliczne. Najdłuższe wątki sond, na których stoją wyniki
# węzła osób, miały 5,9 tys. znaków; dłuższej części nikt nie mierzył.
CHUNK_CHARS = 6000


class SplitChunksNode(Node):
    """
    Description:
    Węzeł grafu, który dzieli tekst po wzorcach na części dla modelu; przebieg opisuje docstring
    modułu.
    """

    name = "split_chunks"

    async def run(
        self,
        state: BaseModel,  # np. AnonymizeState(after_patterns="Od: Bogumił Cieślak <{EMAIL}>…")
    ) -> dict[str, Any]:
        """
        Description:
        Dzieli `after_patterns` na części i zapisuje je w `chunks`; w logu liczba części
        i długość najdłuższej.

        Example args:
            state=AnonymizeState(after_patterns="Od: Bogumił Cieślak <{EMAIL}>…")

        Example result:
            {"chunks": ["Od: Bogumił Cieślak <{EMAIL}>…"],
             "log": [LogEntry(node="split_chunks", message="1 części, najdłuższa 412 zn.")]}
        """
        chunks  = split_into_chunks(state.after_patterns, CHUNK_CHARS)
        longest = max(len(chunk) for chunk in chunks)

        update = {
            "chunks": chunks,
            "log":    [self.log_entry(f"{len(chunks)} części, najdłuższa {longest} zn.")],
        }

        return update
