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

- Rozpoznanie pustego pola należy do `normalizer_sentinel.py` — tam leżą frazy, próg i uwaga
  o sprzężeniu z promptem parsującym. Reguła tutaj robi z tej odpowiedzi dowód do raportu.
- Reguły patrzą tylko na `solution`, nigdy na `cause`. Puste `cause` ma większość dobrych
  rekordów (105 ze 114 na próbce 200), więc filtr po tym polu wyciąłby dużą część korpusu.
"""

from app.core_service.normalizer_sentinel import no_solution

# Ile znaków `solution` trafia do raportu jako dowód.
EVIDENCE_LENGTH = 80


def no_resolution(
    solution: str,  # np. "Brak rozstrzygnięcia w wątku."
) -> str | None:
    """
    Description:
    Odpala, gdy `solution` przyznaje, że rozstrzygnięcia nie ma, i niewiele poza tym dodaje
    (`no_solution()`). Zwraca wtedy pierwsze 80 znaków pola (`EVIDENCE_LENGTH`) jako dowód do
    raportu; w przeciwnym razie None i rekord przechodzi.

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
    if not no_solution(solution):
        return None

    return solution.strip()[:EVIDENCE_LENGTH]


# Reguły w kolejności raportu; po tej krotce iterują orkiestrator i testy.
# Jedna celowo: wzorce na pozostałe odrzucenia (obietnica w czasie przyszłym, odesłanie do innego
# zgłoszenia, kilka spraw w jednym) łapały po 1–2 rekordy i zależały od sformułowań jednego modelu.
RULES = (
    no_resolution,
)
