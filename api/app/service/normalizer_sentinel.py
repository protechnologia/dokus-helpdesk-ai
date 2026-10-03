"""
Description:
Normalizacja sentineli: rozpoznaje pola sparsowanego zgłoszenia, które mówią „nic tu nie ma"
własnymi słowami. Parser ma w takim wypadku wpisać dosłownie `brak`, ale często pisze całe zdanie,
które wygląda jak treść — tu wszystkie te zapisy sprowadzają się do jednej odpowiedzi tak/nie.

| funkcja         | pole       | kto woła                                        | na golden200 |
|-----------------|------------|-------------------------------------------------|--------------|
| `no_solution()` | `solution` | reguła `no_resolution` filtra jakości           | 29 rekordów  |
| `no_cause()`    | `cause`    | blok przyczyn w narzędziu `find_tickets_vector` | 98 rekordów  |

Przykłady:

    no_solution("brak")                                          -> True
    no_solution("Brak rozstrzygnięcia w wątku.")                 -> True
    no_solution("Brak możliwości wygenerowania ZPO w tej
                 sytuacji. Klient musi zaakceptować…")            -> False, odmowa to treść
    no_cause("Brak ustalonej przyczyny w wątku.")                -> True
    no_cause("Brak uprawnienia do kancelarii")                   -> False, to realna przyczyna

Każde pole ma własną regułę, bo to samo zdanie znaczy w nich co innego: „Brak uprawnienia do
kancelarii" jest pełnoprawną przyczyną, a jako rozwiązanie nie mówi nic.

Moduł niczego nie zapisuje: artefakty w `data/parsed/` i payload Qdranta zostają w brzmieniu
parsera, a wołający sam decyduje, co zrobić z odpowiedzią (odrzucić rekord, pokazać
„(nie ustalono)").

O czym pamiętać przy zmianach:

- Frazy są sprzężone z promptem parsującym: reguły czytają to, co prompt każe modelowi wpisać,
  gdy wartości nie ma. Zmiana tych fraz w `graph/parse_ticket/respond_tool.md` jest zmianą tego
  modułu; rozjazd łapie test na korpusie odniesienia w `tests/evaluation/`.
- Sam początek „brak" niczego nie rozstrzyga: zaczyna się od niego wiele realnych przyczyn.
- Liczby w tabelce należą do tego korpusu i tego parsera; po masowym imporcie (p. 31) trzeba je
  zmierzyć od nowa.
"""

import re

from app.model.ticket_parsed import NO_VALUE, NOT_APPLICABLE

# Frazy ucieczkowe: `brak` i `nie dotyczy` to jawne wyjścia schematu, dwie pozostałe parser pisze
# obok nich. `brak` tylko jako całe słowo: „Dodano brakujące ustawienie" to wykonana praca.
ESCAPE_PHRASE = re.compile(r"\b(brak|nie dotyczy|nie ustalono|nie podano)\b", re.IGNORECASE)

# Ile słów może zostać w `solution` obok frazy ucieczkowej, żeby pole nadal liczyło się jako puste.
# Na 200 rekordach każda wartość 4–10 dzieli tak samo.
MAX_HOLLOW_EXTRA_WORDS = 10

# „Brak", najwyżej trzy słowa, potem słowo zaczynające się od „przyczyn".
NO_CAUSE_PHRASE = re.compile(r"^\s*brak\s+(?:\w+\s+){0,3}przyczyn", re.IGNORECASE)


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


def no_cause(
    cause: str,  # np. "Brak ustalonej przyczyny w wątku."
) -> bool:
    """
    Description:
    Mówi, czy `cause` stwierdza, że przyczyny nie ustalono: jawnym wyjściem schematu (`brak`,
    `nie dotyczy`) albo zdaniem „brak … przyczyny".

    Example args:
        cause="Brak ustalonej przyczyny w wątku."

    Example result:
        True
    """
    # --- jawne wyjście schematu: „brak", „Brak.", „nie dotyczy" ---
    if cause.strip().rstrip(".").casefold() in (NO_VALUE, NOT_APPLICABLE):
        return True

    # --- zdanie stwierdzające, że przyczyny nie ustalono ---
    return bool(NO_CAUSE_PHRASE.search(cause))
