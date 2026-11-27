"""
Description:
Zestaw bramki zamknięcia na prawdziwych zamknięciach (`graph-gate-close.json`, p. 33.2). Wpis to
jedno zamknięcie z korpusu instancji: warstwa doboru, liczba komentarzy w chwili zamknięcia, skrót
uciętego wątku i dwie etykiety, po jednej na regułę zamknięcia. Wejście bramki test składa
z wątku po anonimizacji, uciętego tak, jak go widział konsultant, który zamykał zgłoszenie.

| funkcja                              | do czego                                              |
|--------------------------------------|-------------------------------------------------------|
| `golden_gate_close_cases()`          | wpisy zestawu w kolejności pliku                      |
| `golden_gate_close_rules_version()`  | wersja reguł bramki, pod którą oznaczano zestaw       |
| `thread_at_close()`                  | wątek ucięty po podanej liczbie komentarzy            |
| `closing_thread()`                   | wątek zgłoszenia z korpusu, ucięty na zamknięciu      |
| `thread_digest()`                    | skrót uciętego wątku; pilnuje, że etykiety opisują go |
| `judge_gate_close_case()`            | ocena werdyktu bramki wobec etykiet wpisu             |
| `timing_summary()`                   | mediana, p90 i maksimum czasu spraw                   |

Grupy wpisów (`GoldenGateCloseCase.group`):

| grupa         | wpis                                        | werdykt           | zły werdykt to |
|---------------|---------------------------------------------|-------------------|----------------|
| `pass`        | sprawa: widać problem i rozwiązanie         | `pass`            | fałszywy alarm |
| `no_problem`  | sprawa: nie widać problemu                  | `block`           | przepuszczenie |
| `no_solution` | sprawa: nie widać rozwiązania               | `block`           | przepuszczenie |
| `neither`     | sprawa: nie widać ani jednego, ani drugiego | `block`           | przepuszczenie |
| `notice`      | powiadomienie, bez względu na reguły        | `block` (ADR-005) | przepuszczenie |

O czym pamiętać przy zmianach:

- Ucięcie liczy się po nagłówkach komentarzy z `RawTicket.as_thread()` („KOMENTARZ N — …”);
  gdy zmieni się ich brzmienie, skrót każdego wpisu przestanie się zgadzać i test spójności to
  pokaże.
- Odpowiedź nie do przyjęcia nie jest ani fałszywym alarmem, ani przepuszczeniem: helpdesk
  dostaje wtedy 503 i decyduje sam. Liczy się osobno.
"""

import hashlib
import json
import math
import re
import statistics
from collections.abc import Sequence

from pydantic import BaseModel

from tests._helpers.golden_gate_close.constants import ANONYMIZED_DIR, GOLDEN_FILE
from tests._helpers.golden_gate_close.models.gate_close_outcome import GateCloseOutcome
from tests._helpers.golden_gate_close.models.golden_gate_close_case import GoldenGateCloseCase
from tests._helpers.golden_gate_close.models.timing_summary import TimingSummary

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


def golden_gate_close_rules_version() -> int:
    """
    Description:
    Czyta z metryczki zestawu wersję reguł bramki zamknięcia, pod którą oznaczano wpisy. Pomiar
    porównuje ją z zestawem domyślnym, zanim zawoła model: etykiety pod inne reguły nic nie
    mierzą.

    Example args:
        (brak)

    Example result:
        1
    """
    meta = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["meta"]

    return meta["rules_version"]


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


def judge_gate_close_case(
    case:    GoldenGateCloseCase,  # np. GoldenGateCloseCase(ticket_id="33605", …)
    output:  BaseModel | None,     # np. Verdict(verdict="block", …); None — `respond` nie przyjął
    retries: int,                  # np. 0 — poprawki odpowiedzi od węzła `respond`
    seconds: float,                # np. 3.2 — ile trwała sprawa bramki
) -> GateCloseOutcome:
    """
    Description:
    Ocenia jedno zamknięcie: zapisuje werdykt, pola wyniku do raportu i czas sprawy, a brak
    wyniku jako odpowiedź nie do przyjęcia. Czy to fałszywy alarm, czy przepuszczenie, mówi
    ocena, porównując werdykt z grupą wpisu.

    Example args:
        case=GoldenGateCloseCase(ticket_id="33605", kind="sprawa", problem_visible=True,
                                 action_visible=False, …)
        output=Verdict(verdict="pass")
        retries=0
        seconds=3.2

    Example result:
        GateCloseOutcome(case=GoldenGateCloseCase(ticket_id="33605", …), answer="pass",
                         retries=0, fields={"verdict": "pass", "reasons": [], "hint": None},
                         seconds=3.2)
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = GateCloseOutcome(
            case    = case,
            answer  = None,
            retries = retries,
            fields  = {},
            seconds = seconds,
        )

        return rejected

    fields = output.model_dump(mode="json")

    outcome = GateCloseOutcome(
        case    = case,
        answer  = fields["verdict"],
        retries = retries,
        fields  = fields,
        seconds = seconds,
    )

    return outcome


def timing_summary(
    seconds: Sequence[float],  # np. [2.1, 3.4, 9.8] — czasy spraw przebiegu
) -> TimingSummary:
    """
    Description:
    Liczy medianę, p90 i maksimum czasu spraw. p90 to wartość, której nie przekracza 90% spraw:
    element z miejsca ⌈0,9 · n⌉ po posortowaniu, bez interpolacji, więc jest czasem prawdziwej
    sprawy.

    Example args:
        seconds=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

    Example result:
        TimingSummary(median=5.5, p90=9.0, maximum=10.0)

    Raises:
        ValueError: lista jest pusta
    """
    if not seconds:
        raise ValueError("brak czasów spraw: nie ma z czego liczyć")

    ordered = sorted(seconds)

    summary = TimingSummary(
        median  = statistics.median(ordered),
        p90     = ordered[math.ceil(0.9 * len(ordered)) - 1],
        maximum = ordered[-1],
    )

    return summary
