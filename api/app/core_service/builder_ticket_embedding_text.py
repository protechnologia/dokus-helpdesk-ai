"""
Description:
Składa tekst, z którego embedder liczy wektor zgłoszenia: `problem` i `symptoms`, każde w swojej
linii. Jedyne miejsce, które to robi — wołają je obie strony porównania:

| strona     | kto woła                        | tryb embeddera |
|------------|---------------------------------|----------------|
| indeksacja | `ParsedTicket.embedding_text()` | passage        |
| zapytanie  | narzędzie `find_tickets_vector` | query          |

Przed — dwa pola:

    problem  = "Wysyłka przez ePUAP kończy się błędem komunikacji"
    symptoms = "Po kliknięciu Wyślij pojawia się komunikat o braku sieci"

Po — jeden tekst:

    "Wysyłka przez ePUAP kończy się błędem komunikacji\\nPo kliknięciu Wyślij pojawia się…"

O czym pamiętać przy zmianach:

- Zmiana tej funkcji zmienia wektory po obu stronach, więc wymaga pełnego re-indeksu
  (`helpdesk rag reindex`).
- `solution` celowo tu nie ma: szukamy po podobieństwie problemu, nie rozwiązania.
"""


def build_embedding_text(
    problem:  str,  # np. "Wysyłka przez ePUAP kończy się błędem komunikacji"
    symptoms: str,  # np. "Po kliknięciu Wyślij pojawia się komunikat o braku sieci"
) -> str:
    """
    Description:
    Łączy `problem` i `symptoms` w tekst do embeddingu.

    Example args:
        problem="Wysyłka przez ePUAP kończy się błędem komunikacji"
        symptoms="Po kliknięciu Wyślij pojawia się komunikat o braku sieci"

    Example result:
        "Wysyłka przez ePUAP kończy się błędem komunikacji\\nPo kliknięciu Wyślij pojawia się…"
    """
    return f"{problem}\n{symptoms}"
