"""
Description:
Lista reguł filtra jakości, który przy indeksacji (`helpdesk rag index`) decyduje, czy sparsowane
zgłoszenie niesie jakąkolwiek wiedzę i warto je wpuścić do Qdranta.

| reguła          | odpala, gdy                                                    |
|-----------------|----------------------------------------------------------------|
| `no_resolution` | `solution` niesie frazę ucieczkową i najwyżej 10 słów poza nią |

Sam plik niczego nie odrzuca. Robi to orkiestrator `filter_ticket_quality.py`, który iteruje po
krotce `RULES` z końca pliku i składa werdykt oraz raport dla `rag_indexer`. Dołożenie reguły to
dopisanie funkcji, wpisu w `RULES` i wiersza w tabelce; testy parametryzują się po tej krotce.

Dwie rzeczy, o których warto pamiętać przy zmianach:

- Frazy są sprzężone z promptem parsującym. Reguła czyta te sformułowania, które prompt każe
  modelowi wpisać, gdy rozstrzygnięcia nie ma. Zmiana tych fraz w
  `graph/parse_ticket/respond_tool.md` jest zmianą filtra; rozjazd ma wyłapać test na korpusie
  odniesienia (`test_api_service_filter_ticket_quality_corpus.py`).
- Reguły patrzą tylko na `solution`, nigdy na `cause`. Puste `cause` ma większość dobrych
  rekordów (105 ze 114 na próbce 200), więc filtr po tym polu wyciąłby dużą część korpusu.
"""

import re

# Frazy ucieczkowe: `brak` i `nie dotyczy` to jawne wyjścia schematu (NO_VALUE, NOT_APPLICABLE),
# dwie pozostałe parser pisze obok nich.
# `brak` tylko jako całe słowo: „Dodano brakujące ustawienie" to wykonana praca, nie pustka.
ESCAPE_PHRASE = re.compile(r"\b(brak|nie dotyczy|nie ustalono|nie podano)\b", re.I)

# Ile słów może zostać obok frazy ucieczkowej, żeby pole nadal liczyło się jako puste.
# Na 200 rekordach każda wartość 4–10 dzieli tak samo; do przejrzenia na pełnym korpusie.
MAX_HOLLOW_EXTRA_WORDS = 10

# Ile znaków `solution` trafia do raportu jako dowód.
EVIDENCE_LENGTH = 80


def no_resolution(
    solution: str,  # np. "Brak rozstrzygnięcia w wątku."
) -> str | None:
    """
    Description:
    Odpala, gdy `solution` przyznaje, że rozstrzygnięcia nie ma, i niewiele poza tym dodaje.

    1. Szuka w polu `solution` frazy ucieczkowej: „brak", „nie dotyczy", „nie ustalono" albo
       „nie podano" (jako całe słowo). Bez niej rekord przechodzi.
    2. Liczy, ile słów zostaje po jej wycięciu.
    3. Jeśli zostaje najwyżej 10 słów (`MAX_HOLLOW_EXTRA_WORDS`), rekord jest pusty i reguła
       zwraca pierwsze 80 znaków pola (`EVIDENCE_LENGTH`) jako dowód do raportu.
    4. Jeśli zostaje więcej, „brak" otwiera realną treść (np. odmowę z uzasadnieniem), więc
       rekord przechodzi.

    Na 200 rekordach odniesienia reguła łapie 29 z 38 oznaczonych odrzuceń, bez fałszywych
    alarmów.

    Example args:
        solution="Brak rozstrzygnięcia w wątku."

    Example result:
        "Brak rozstrzygnięcia w wątku."

    Example args:
        solution="Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować…"

    Example result:
        None — odmowa to treść, nie pustka
    """
    # --- czy jest fraza ucieczkowa? ---
    if not ESCAPE_PHRASE.search(solution):
        return None

    # --- ile słów zostaje po jej wycięciu? ---
    remainder = ESCAPE_PHRASE.sub(" ", solution)

    if len(re.findall(r"\w+", remainder)) > MAX_HOLLOW_EXTRA_WORDS:
        return None

    return solution.strip()[:EVIDENCE_LENGTH]


# Reguły w kolejności raportu; po tej krotce iterują orkiestrator i testy.
# Jedna celowo: wzorce na pozostałe odrzucenia (obietnica w czasie przyszłym, odesłanie do innego
# zgłoszenia, kilka spraw w jednym) łapały po 1–2 rekordy i zależały od sformułowań jednego modelu.
RULES = (
    no_resolution,
)
