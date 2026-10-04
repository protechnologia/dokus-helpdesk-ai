"""
Description:
Normalizacja sentineli: rozpoznaje pole `solution` sparsowanego zgłoszenia, które mówi „nic tu
nie ma" własnymi słowami. Parser ma w takim wypadku wpisać dosłownie `brak`, ale często pisze
całe zdanie, które wygląda jak treść — tu wszystkie te zapisy sprowadzają się do jednej
odpowiedzi tak/nie. Woła to reguła `no_resolution` filtra jakości (29 rekordów na golden200).

Przykłady:

    no_solution("brak")                                          -> True
    no_solution("Brak rozstrzygnięcia w wątku.")                 -> True
    no_solution("Brak możliwości wygenerowania ZPO w tej
                 sytuacji. Klient musi zaakceptować…")            -> False, odmowa to treść

Moduł niczego nie zapisuje: artefakty w `data/parsed/` i payload Qdranta zostają w brzmieniu
parsera, a wołający sam decyduje, co zrobić z odpowiedzią.

O czym pamiętać przy zmianach:

- Frazy są sprzężone z promptem parsującym: reguła czyta to, co prompt każe modelowi wpisać,
  gdy wartości nie ma. Zmiana tych fraz w `agent_graphs/parse_ticket/respond_tool.md` jest
  zmianą tego modułu; rozjazd łapie test na korpusie odniesienia w `tests/evaluation/`.
- Sam początek „brak" niczego nie rozstrzyga: zaczyna się od niego wiele realnych treści.
- Każde pole potrzebuje własnej reguły, bo to samo zdanie znaczy w nich co innego: „Brak
  uprawnienia do kancelarii" jest pełnoprawną przyczyną, a jako rozwiązanie nie mówi nic.
- Liczba należy do tego korpusu i tego parsera; po masowym imporcie (p. 31) trzeba ją zmierzyć
  od nowa.
"""

import re

# Frazy ucieczkowe: `brak` i `nie dotyczy` to jawne wyjścia schematu, dwie pozostałe parser pisze
# obok nich. `brak` tylko jako całe słowo: „Dodano brakujące ustawienie" to wykonana praca.
ESCAPE_PHRASE = re.compile(r"\b(brak|nie dotyczy|nie ustalono|nie podano)\b", re.IGNORECASE)

# Ile słów może zostać w `solution` obok frazy ucieczkowej, żeby pole nadal liczyło się jako puste.
# Na 200 rekordach każda wartość 4–10 dzieli tak samo.
MAX_HOLLOW_EXTRA_WORDS = 10


def no_solution(
    solution: str,  # np. "Brak rozstrzygnięcia w wątku."
) -> bool:
    """
    Description:
    Mówi, czy `solution` tylko przyznaje, że rozstrzygnięcia nie ma.

    1. Szuka frazy ucieczkowej; bez niej pole niesie treść.
    2. Liczy słowa po jej wycięciu: najwyżej `MAX_HOLLOW_EXTRA_WORDS` — pole jest puste; więcej —
       „brak" otwiera realną treść, np. odmowę z uzasadnieniem.

    Example args:
        solution="Brak rozstrzygnięcia w wątku."

    Example result:
        True
    """
    # --- czy jest fraza ucieczkowa? ---
    if not ESCAPE_PHRASE.search(solution):
        return False

    # --- ile słów zostaje po jej wycięciu? ---
    remainder  = ESCAPE_PHRASE.sub(" ", solution)
    word_count = len(re.findall(r"\w+", remainder))

    return word_count <= MAX_HOLLOW_EXTRA_WORDS
