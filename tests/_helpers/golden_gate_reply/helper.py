"""
Description:
Zestaw bramki wysyłki na prawdziwych wiadomościach (`gate-reply.json`, p. 33.3). Wpis to jedna
wiadomość konsultanta z korpusu instancji: zgłoszenie, numer komentarza, warstwa doboru, skrót
wiadomości i reguły, które według oceniających łamie, każda z powodem. Wejście bramki test wycina
z wątku po anonimizacji, tak jak stoi w korpusie.

| funkcja                             | do czego                                                 |
|-------------------------------------|----------------------------------------------------------|
| `golden_gate_reply_cases()`         | wpisy zestawu w kolejności pliku                         |
| `golden_gate_reply_rules_version()` | wersja reguł bramki, pod którą oznaczano zestaw          |
| `consultant_message()`              | treść komentarza konsultanta z tekstu wątku              |
| `corpus_message()`                  | to samo dla wątku z korpusu instancji                    |
| `message_digest()`                  | skrót wiadomości; pilnuje, że etykiety opisują ten tekst |

O czym pamiętać przy zmianach:

- Komentarz wycina się po nagłówkach z `RawTicket.as_thread()` („KOMENTARZ N — rola, data
  (typ: …):”); gdy zmieni się ich brzmienie, skrót każdego wpisu przestanie się zgadzać i test
  spójności to pokaże.
"""

import hashlib
import json
import re

from tests._helpers.golden_gate_reply.constants import ANONYMIZED_DIR, CONSULTANT_ROLE, GOLDEN_FILE
from tests._helpers.golden_gate_reply.models.golden_gate_reply_case import GoldenGateReplyCase
from tests._helpers.golden_gate_reply.models.rule_violation import RuleViolation

# Nagłówek komentarza w tekście wątku, tak jak pisze go `RawTicket.as_thread()`: numer, rola,
# data i typ, a treść zaczyna się w następnej linii.
COMMENT_HEADER = re.compile(r"(?m)^KOMENTARZ (\d+) — ([^,\n]+), [^\n]* \(typ: [a-z_]+\):\n")


def golden_gate_reply_cases() -> list[GoldenGateReplyCase]:
    """
    Description:
    Czyta wpisy zestawu w kolejności pliku.

    Example args:
        (brak)

    Example result:
        [GoldenGateReplyCase(ticket_id="23921", comment=2, stratum="keywords",
            digest="ad7c2f36723bdde1", violations=(RuleViolation(rule=6, reason="…"),),
            doubtful=False, doubt=None), …]
    """
    raw   = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    cases = [
        GoldenGateReplyCase(
            ticket_id  = entry["ticket_id"],
            comment    = entry["comment"],
            stratum    = entry["stratum"],
            digest     = entry["digest"],
            violations = tuple(
                RuleViolation(rule=violation["rule"], reason=violation["reason"])
                for violation in entry["violations"]
            ),
            doubtful   = entry["doubtful"],
            doubt      = entry["doubt"],
        )
        for entry in raw["messages"]
    ]

    return cases


def golden_gate_reply_rules_version() -> int:
    """
    Description:
    Czyta z metryczki zestawu wersję reguł bramki wysyłki, pod którą oznaczano wpisy. Pomiar
    porównuje ją z zestawem domyślnym, zanim zawoła model: etykiety pod inne reguły nic nie
    mierzą.

    Example args:
        (brak)

    Example result:
        3
    """
    meta = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["meta"]

    return meta["rules_version"]


def consultant_message(
    thread:  str,  # np. "ZGŁOSZENIE 33644 z 2026-06-23\nTemat: …\n\nKOMENTARZ 1 — konsultant, …"
    comment: int,  # np. 2 — numer komentarza w wątku, od 1
) -> str:
    """
    Description:
    Wycina z tekstu wątku treść komentarza o podanym numerze: od linii po nagłówku do pustej
    linii przed następnym nagłówkiem albo do końca wątku. Komentarz musi być konsultanta, bo
    bramka ocenia wiadomość, którą konsultant wysyła klientowi.

    Example args:
        thread="ZGŁOSZENIE 1 z 2026-01-02\\nTemat: T\\n\\nOPIS ZGŁASZAJĄCEGO:\\nO\\n\\n
                KOMENTARZ 1 — konsultant, 2026-01-02 10:00:00 (typ: rozwiazanie):\\nA\\nB"
        comment=1

    Example result:
        "A\\nB"

    Raises:
        ValueError: nagłówki nie idą po kolei, wątek nie ma takiego komentarza albo napisał go
            ktoś inny niż konsultant
    """
    # --- sprawdź nagłówki ---
    # Numery muszą iść od 1 bez przerw: inaczej numer wpisu wskazałby inny komentarz.
    headers = list(COMMENT_HEADER.finditer(thread))
    numbers = [int(match.group(1)) for match in headers]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"nagłówki komentarzy nie idą po kolei: {numbers}")
    if not 1 <= comment <= len(headers):
        raise ValueError(f"wątek ma {len(headers)} komentarzy, a wpis wskazuje {comment}")

    header = headers[comment - 1]
    if header.group(2) != CONSULTANT_ROLE:
        raise ValueError(f"komentarz {comment} napisał {header.group(2)!r}, a nie konsultant")

    # --- wytnij treść ---
    # `as_thread()` stawia pustą linię przed każdym nagłówkiem, więc ona do treści nie należy.
    end  = headers[comment].start() if comment < len(headers) else len(thread)
    body = thread[header.end():end].rstrip("\n")

    return body


def corpus_message(
    ticket_id: str,  # np. "23921"
    comment:   int,  # np. 2 — numer komentarza w wątku, od 1
) -> str:
    """
    Description:
    Czyta wątek zgłoszenia po anonimizacji z korpusu instancji i wycina z niego wiadomość
    konsultanta o podanym numerze.

    Example args:
        ticket_id="23921"
        comment=2

    Example result:
        "Dzień dobry,\\n\\nzgodnie z ustaleniami telefonicznymi …"

    Raises:
        FileNotFoundError: korpus nie ma wątku tego zgłoszenia
        ValueError: wątek nie ma takiego komentarza albo napisał go ktoś inny niż konsultant
    """
    thread = (ANONYMIZED_DIR / f"{ticket_id}.txt").read_text(encoding="utf-8")

    return consultant_message(thread, comment)


def message_digest(text: str) -> str:   # np. "Dzień dobry,\n\nkonto zostało odblokowane."
    """
    Description:
    Liczy skrót wiadomości (BLAKE2b, 8 bajtów). Wpis zestawu zapisuje go obok etykiet: gdy
    zamknięcie przez trasę nadpisze wątek w korpusie albo zmieni się wycinanie, skrót to pokaże,
    zanim test zmierzy bramkę na tekście, którego oceniający nie widzieli.

    Example args:
        text="Dzień dobry."

    Example result:
        "a2d4c66de139ad2f"
    """
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
