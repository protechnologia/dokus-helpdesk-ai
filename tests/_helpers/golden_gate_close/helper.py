"""
Description:
Zestaw bramki zamknięcia na prawdziwych zamknięciach (`gate-close.json`, p. 33.2). Wpis to jedno
zamknięcie z korpusu instancji: warstwa doboru, liczba komentarzy w chwili zamknięcia, skrót
uciętego wątku i dwie etykiety, po jednej na regułę zamknięcia. Wejście bramki test składa
z wątku po anonimizacji, uciętego tak, jak go widział konsultant, który zamykał zgłoszenie.

| funkcja                     | do czego                                                     |
|-----------------------------|--------------------------------------------------------------|
| `golden_gate_close_cases()` | wpisy zestawu w kolejności pliku                             |
| `thread_at_close()`         | wątek ucięty po podanej liczbie komentarzy                   |
| `closing_thread()`          | wątek zgłoszenia z korpusu, ucięty na zamknięciu             |
| `thread_digest()`           | skrót uciętego wątku, którym etykiety pilnują, że opisują go |

O czym pamiętać przy zmianach: ucięcie liczy się po nagłówkach komentarzy z
`RawTicket.as_thread()` („KOMENTARZ N — …”); gdy zmieni się ich brzmienie, skrót każdego wpisu
przestanie się zgadzać i test spójności to pokaże.
"""

import hashlib
import json
import re

from tests._helpers.golden_gate_close.constants import ANONYMIZED_DIR, GOLDEN_FILE
from tests._helpers.golden_gate_close.models.golden_gate_close_case import GoldenGateCloseCase

# Nagłówek komentarza w tekście wątku, tak jak pisze go `RawTicket.as_thread()`.
COMMENT_HEADER = re.compile(r"(?m)^KOMENTARZ (\d+) — ")


def golden_gate_close_cases() -> list[GoldenGateCloseCase]:
    """
    Description:
    Czyta wpisy zestawu w kolejności pliku.

    Example args:
        (brak)

    Example result:
        [GoldenGateCloseCase(ticket_id="33605", stratum="random", comments_at_close=2,
            digest="ad7c2f36723bdde1", kind="sprawa", problem_visible=True, problem_reason="…",
            action_visible=False, action_reason="…", doubtful=False), …]
    """
    raw   = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    cases = [
        GoldenGateCloseCase(
            ticket_id         = entry["ticket_id"],
            stratum           = entry["stratum"],
            comments_at_close = entry["comments_at_close"],
            digest            = entry["digest"],
            kind              = entry["kind"],
            problem_visible   = entry["problem_visible"],
            problem_reason    = entry["problem_reason"],
            action_visible    = entry["action_visible"],
            action_reason     = entry["action_reason"],
            doubtful          = entry["doubtful"],
        )
        for entry in raw["tickets"]
    ]

    return cases


def thread_at_close(
    thread:   str,  # np. "ZGŁOSZENIE 33644 z 2026-06-23\nTemat: …\n\nKOMENTARZ 1 — …"
    comments: int,  # np. 2 — ile komentarzy stało w wątku w chwili zamknięcia
) -> str:
    """
    Description:
    Ucina tekst wątku po podanej liczbie komentarzy: zostaje nagłówek zgłoszenia, opis
    i komentarze od pierwszego do `comments`. Przy liczbie równej liczbie komentarzy wątek wraca
    bez zmian; przy zerze zostaje sam opis.

    Example args:
        thread="ZGŁOSZENIE 1 z 2026-01-02\nTemat: T\n\nOPIS ZGŁASZAJĄCEGO:\nO\n\n
                KOMENTARZ 1 — konsultant, 2026-01-02 10:00:00 (typ: rozwiazanie):\nA"
        comments=0

    Example result:
        "ZGŁOSZENIE 1 z 2026-01-02\nTemat: T\n\nOPIS ZGŁASZAJĄCEGO:\nO"

    Raises:
        ValueError: wątek ma mniej komentarzy, niż podano, albo nagłówki nie idą po kolei
    """
    # --- sprawdź nagłówki ---
    # Numery muszą iść od 1 bez przerw: inaczej ucięcie po numerze trafiłoby w złe miejsce.
    headers = list(COMMENT_HEADER.finditer(thread))
    numbers = [int(match.group(1)) for match in headers]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"nagłówki komentarzy nie idą po kolei: {numbers}")
    if comments > len(headers):
        raise ValueError(f"wątek ma {len(headers)} komentarzy, a zamknięcie wymaga {comments}")

    # --- utnij ---
    # Wszystkie komentarze stały w chwili zamknięcia: nie ma czego ucinać.
    if comments == len(headers):
        return thread

    # Ucięcie przed nagłówkiem pierwszego komentarza po zamknięciu, bez pustej linii przed nim.
    cut = thread[:headers[comments].start()].rstrip("\n")

    return cut


def closing_thread(
    ticket_id: str,  # np. "33605"
    comments:  int,  # np. 2 — ile komentarzy stało w wątku w chwili zamknięcia
) -> str:
    """
    Description:
    Czyta wątek zgłoszenia po anonimizacji z korpusu instancji i ucina go na zamknięciu.

    Example args:
        ticket_id="33605"
        comments=2

    Example result:
        "ZGŁOSZENIE 33605 z 2026-07-02\nTemat: …\n\nOPIS ZGŁASZAJĄCEGO:\n…"

    Raises:
        FileNotFoundError: korpus nie ma wątku tego zgłoszenia
        ValueError: wątek ma mniej komentarzy, niż podano
    """
    thread = (ANONYMIZED_DIR / f"{ticket_id}.txt").read_text(encoding="utf-8")

    return thread_at_close(thread, comments)


def thread_digest(text: str) -> str:   # np. "ZGŁOSZENIE 33605 z 2026-07-02\nTemat: …"
    """
    Description:
    Liczy skrót uciętego wątku (BLAKE2b, 8 bajtów). Wpis zestawu zapisuje go obok etykiet: gdy
    zamknięcie przez trasę nadpisze wątek w korpusie albo zmieni się ucięcie, skrót to pokaże,
    zanim test zmierzy bramkę na tekście, którego oceniający nie widział.

    Example args:
        text="ZGŁOSZENIE 1 z 2026-01-02\\nTemat: T"

    Example result:
        "46266d8496d232c3"
    """
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
