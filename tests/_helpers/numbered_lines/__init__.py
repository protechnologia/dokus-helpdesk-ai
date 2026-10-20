"""
Description:
Linie z numerami w testach odczytu kodu: `numbered_pairs()` rozbiera pole `numbered_lines`
z wyniku `read_code_file` i `read_code_symbol` z powrotem na pary „numer, treść", a
`line_numbers()` i `line_texts()` oddają same numery albo samą treść — żeby test porównał je
z liniami pliku. Używają go testy obu narzędzi i ich atrap.

Logika leży w `helper.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.numbered_lines.helper import line_numbers, line_texts, numbered_pairs

__all__ = [
    "line_numbers",
    "line_texts",
    "numbered_pairs",
]
