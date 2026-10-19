"""
Description:
Węzeł `replace_patterns`, pierwszy w grafie anonimizacji: zamiana danych o stałym kształcie na
znaczniki. Przepuszcza tekst przez wszystkie warianty wszystkich wzorców, wybiera miejsca, które
na siebie nie zachodzą, i zamienia każde na znacznik jego rodzaju (`{PESEL}`, `{ADRES}`…). Osoby
i adresy bez kotwicy wskazuje dopiero model, w kolejnych węzłach (p. 19.5).

Przykład:

    przed: „Pani Barbara, PESEL 85030512840, tel. 600 100 200, ul. Lipowa 12/4, 21-100 Lubartów”
    po:    „Pani Barbara, PESEL {PESEL}, tel. {TELEFON}, ul. {ADRES}”

Kroki:

1. Każdy wariant z `VARIANTS` zwraca swoje miejsca.
2. Miejsca układają się od najdłuższego; przy równej długości wygrywa wariant wcześniejszy
   w `PATTERNS`, a potem miejsce wcześniejsze w tekście.
3. Po kolei bierze się każde miejsce, które nie zachodzi na wzięte wcześniej.
4. Wzięte miejsca zamienia się od końca tekstu, żeby zamiana nie przesuwała pozostałych.

O czym pamiętać przy zmianach:

- Najdłuższe wygrywa, bo dłuższe znalezisko niesie krótsze w sobie: adres z kodem pocztowym
  zawiera ulicę z numerem, a e-mail — imię i nazwisko.
- Wzorce z sumą kontrolną stoją w `PATTERNS` przed telefonem: dziewięć cyfr z poprawną sumą
  REGON-u to REGON, choć mają też kształt telefonu.
- Nowy plik wzorca w `core_patterns/` trzeba dopisać do `PATTERNS`; test zamiany pilnuje, że
  żadnego nie brakuje.
"""

from collections import Counter
from typing import Any

from pydantic import BaseModel

from anonymizer_app.agent_nodes.base import Node
from anonymizer_app.core_model.found import Found
from anonymizer_app.core_patterns import (
    address,
    bank_account,
    edor,
    email,
    id_card,
    nip,
    passport,
    pesel,
    phone_number,
    regon,
)
from anonymizer_app.core_service.replacer_found import choose_found, replace_found

# Wzorce w kolejności, która rozstrzyga remis dwóch miejsc tej samej długości.
PATTERNS = (
    email,
    edor,
    bank_account,
    regon,
    pesel,
    nip,
    id_card,
    passport,
    phone_number,
    address,
)

# Warianty wszystkich wzorców w tej samej kolejności.
VARIANTS = tuple(variant for pattern in PATTERNS for variant in pattern.VARIANTS)


def find_patterns(
    text: str,  # np. "PESEL 85030512840, tel. 600 100 200"
) -> list[Found]:
    """
    Description:
    Miejsca danych o stałym kształcie, które na siebie nie zachodzą, w kolejności tekstu.
    Kolejne kroki opisuje docstring modułu.

    Example args:
        text="PESEL 85030512840, tel. 600 100 200"

    Example result:
        [Found(kind="PESEL", start=6, end=17), Found(kind="TELEFON", start=24, end=35)]
    """
    # Numer wariantu to priorytet przy remisie długości: wcześniejszy wzorzec wygrywa.
    candidates = [
        (found, order)
        for order, variant in enumerate(VARIANTS)
        for found in variant(text)
    ]

    return choose_found(candidates)


def replace_patterns(
    text: str,  # np. "PESEL 85030512840, tel. 600 100 200"
) -> str:
    """
    Description:
    Zamienia każde miejsce z `find_patterns()` na znacznik jego rodzaju i nie rusza niczego
    więcej.

    Example args:
        text="PESEL 85030512840, tel. 600 100 200"

    Example result:
        "PESEL {PESEL}, tel. {TELEFON}"
    """
    return replace_found(text, find_patterns(text))


class ReplacePatternsNode(Node):
    """
    Description:
    Węzeł grafu, który zamienia dane o stałym kształcie wzorcami; przebieg opisuje docstring
    modułu. Stoi pierwszy, więc kroki z modelem dostają tekst bez numerów, e-maili i adresów
    z kotwicą.
    """

    name = "replace_patterns"

    async def run(
        self,
        state: BaseModel,  # np. AnonymizeState(input_text="PESEL 85030512840, tel. 600 100 200")
    ) -> dict[str, Any]:
        """
        Description:
        Zamienia wzorcami tekst z wejścia i zapisuje wynik w `after_patterns`; w logu liczba
        miejsc na rodzaj.

        Example args:
            state=AnonymizeState(input_text="PESEL 85030512840, tel. 600 100 200")

        Example result:
            {"after_patterns": "PESEL {PESEL}, tel. {TELEFON}",
             "log": [LogEntry(node="replace_patterns", message="2 miejsc: PESEL 1, TELEFON 1")]}
        """
        found   = find_patterns(state.input_text)
        kinds   = Counter(place.kind for place in found)
        counts  = ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items()))
        message = f"{len(found)} miejsc: {counts}" if counts else "0 miejsc"

        update = {
            "after_patterns": replace_found(state.input_text, found),
            "log":            [self.log_entry(message)],
        }

        return update
