"""
Description:
Zmyślone zamknięte zgłoszenie do testów serwisu `ClosedTicketIndexer` i trasy
`POST /tickets/closed`: zgłoszenie z trasy, jego wątek po anonimizacji i karta, żądanie do trasy
z tym samym zgłoszeniem oraz werdykty bramki. Pakiet helpera tego pliku nie wystawia — test
importuje próbki z tego modułu.
"""

from datetime import date
from typing import Any

from app.core_model.graphs.verdict import Verdict
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.raw_comment import RawComment
from app.core_model.tickets.raw_ticket import RawTicket
from app.engine_anonymization import AnonymizedText

# Numer zmyślonego zgłoszenia — wspólny dla zgłoszenia, wątku i karty.
TICKET_ID = "41002"

# Zmyślona osoba w zgłoszeniu i jej znaczniki w wątku po anonimizacji: po nich test widzi, czy do
# indeksu poszedł tekst po anonimizacji, a nie surowy.
PERSON         = "Anna Nowak"
PERSON_MARKERS = "{IMIĘ} {NAZWISKO}"


def sample_raw_ticket(
    ticket_id: str = TICKET_ID,  # np. "41003" — gdy test potrzebuje innego numeru
) -> RawTicket:
    """
    Description:
    Zwraca zmyślone zgłoszenie z trasy: brak przesyłek z e-Doręczeń i komentarz konsultanta
    z przyczyną i naprawą.

    Example args:
        ticket_id="41002"

    Example result:
        RawTicket(ticket_id="41002", subject="Brak przesyłek z e-Doręczeń", …)
    """
    ticket = RawTicket(
        ticket_id = ticket_id,
        date      = date(2026, 11, 11),
        category  = "Błąd",
        subject   = "Brak przesyłek z e-Doręczeń",
        body      = "Od wczoraj nie przychodzą przesyłki z e-Doręczeń.",
        comments  = [
            RawComment(
                kind       = "zwyczajny",
                role       = "konsultant",
                created_at = "2026-11-11 10:00:00",
                body       = "Kolejka odbioru stała po awarii; po wznowieniu przesyłki doszły, "
                             f"potwierdziła {PERSON}.",
            ),
        ],
    )

    return ticket


def sample_thread(
    ticket_id: str = TICKET_ID,  # np. "41002"
) -> AnonymizedText:
    """
    Description:
    Zwraca wątek zmyślonego zgłoszenia w kształcie `RawTicket.as_thread()`, po anonimizacji:
    osoba ze zgłoszenia stoi w nim jako znaczniki.

    Example args:
        ticket_id="41002"

    Example result:
        AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\\n…potwierdziła {IMIĘ} {NAZWISKO}.")
    """
    text = sample_raw_ticket(ticket_id).as_thread().replace(PERSON, PERSON_MARKERS)

    return AnonymizedText(text=text)


def sample_card(
    **overrides: object,  # np. useful=False — pola karty do zmiany
) -> ParsedTicket:
    """
    Description:
    Zwraca kartę zmyślonego zgłoszenia, przydatną, chyba że test zmieni pola.

    Example args:
        useful=False
        useful_reason="Wątek tylko potwierdza zamknięcie."

    Example result:
        ParsedTicket(ticket_id="41002", useful=False, …)
    """
    fields = {
        "ticket_id":                     TICKET_ID,
        "date":                          date(2026, 11, 11),
        "component":                     "e-Doręczenia",
        "problem":                       "Nie przychodzą przesyłki z e-Doręczeń",
        "symptoms":                      "Od wczoraj skrzynka nie pobiera nowych przesyłek",
        "error_codes":                   [],
        "cause":                         "Kolejka odbioru zatrzymana po awarii",
        "excluded_causes":               [],
        "solution":                      "Wznowiono kolejkę odbioru; zaległe przesyłki doszły.",
        "resolution":                    "naprawione",
        "resolution_vocabulary_version": 1,
        "parser_model":                  "gpt-6.1-sol",
        "useful":                        True,
        "useful_reason":                 "Wątek podaje przyczynę i sposób naprawy.",
        **overrides,
    }

    return ParsedTicket(**fields)


def sample_request(
    ticket_id: str = TICKET_ID,  # np. "41003" — gdy test potrzebuje innego numeru
) -> dict[str, Any]:
    """
    Description:
    Zwraca treść żądania do trasy zamknięcia z tym samym zgłoszeniem co `sample_raw_ticket()`:
    trasa robi z niego dokładnie to zgłoszenie.

    Example args:
        ticket_id="41002"

    Example result:
        {"ticket_id": "41002", "date": "2026-11-11", "subject": "Brak przesyłek…", …}
    """
    raw = sample_raw_ticket(ticket_id)

    request = {
        "ticket_id": raw.ticket_id,
        "date":      raw.date.isoformat(),
        "category":  raw.category,
        "subject":   raw.subject,
        "body":      raw.body,
        "comments":  [
            {"role": comment.role, "created_at": comment.created_at, "body": comment.body}
            for comment in raw.comments
        ],
    }

    return request


def sample_pass() -> Verdict:
    """
    Description:
    Zwraca werdykt bramki, który przepuszcza zamknięcie.

    Example args:
        (brak)

    Example result:
        Verdict(verdict="pass", reasons=[], hint="")
    """
    return Verdict(verdict="pass")


def sample_block() -> Verdict:
    """
    Description:
    Zwraca werdykt bramki, który blokuje zamknięcie, z uzasadnieniem i wskazówką.

    Example args:
        (brak)

    Example result:
        Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz, …")
    """
    verdict = Verdict(
        verdict = "block",
        reasons = ["Nie widać, co zrobiono."],
        hint    = "Dopisz, co zmieniono w kolejce odbioru.",
    )

    return verdict
