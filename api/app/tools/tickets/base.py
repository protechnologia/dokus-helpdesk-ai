"""
Description:
Tekst, którym narzędzia zgłoszeń pokazują modelowi zgłoszenie w obu postaciach: kartę
(`find_tickets_vector`) i oryginalny wątek (`find_tickets_text`). Jedno miejsce, żeby karta
i wątek wyglądały tak samo w każdym narzędziu, które je pokaże.

Karty. Przed — nagłówek narzędzia i zgłoszenia z informacją, jak każde znaleziono:

    header  = "Znalezione zgłoszenia: 2 (odcięte progiem: 1)"
    entries = [
        (ParsedTicket(ticket_id="90001", …), "podobieństwo 0.91"),
        (ParsedTicket(ticket_id="90003", …), "podobieństwo 0.86"),
    ]

Po — tekst dla modelu:

    Znalezione zgłoszenia: 2 (odcięte progiem: 1)

    [90001] 2026-02-10 · podobieństwo 0.91
    component: e-Doręczenia
    problem: Nie przychodzą przesyłki z e-Doręczeń
    symptoms: Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę
    error_codes: (brak)
    cause: Zacięta kolejka pobierania po przerwanym połączeniu
    solution: Zrestartowano kolejkę; zaległe przesyłki pobrały się same.
    resolution: naprawione
    questions_summary: pytano, od kiedy brak przesyłek i czy dotyczy wszystkich skrzynek

    [90003] 2026-06-03 · podobieństwo 0.86
    …

Wątek — oryginalny tekst między dwiema liniami z numerem zgłoszenia:

    --- wątek 90011 ---
    ZGŁOSZENIE 90011 z 2026-03-02
    Temat: Błąd przy podpisie
    …
    --- koniec wątku 90011 ---

Co się dzieje po drodze:

1. Nagłówek przychodzi z narzędzia, bo tylko ono wie, co policzyło (próg albo limit trafień).
2. Rekordy niosą wszystkie pola payloadu pod nazwami ze schematu, bo prompty grafów odwołują się
   do nich po nazwie (`cause`, `solution`, `questions_summary`).

O czym pamiętać przy zmianach:

- Ten tekst jest częścią promptu: jego kształt stroi się pomiarem razem z promptami grafów
  (p. 23, 25–26), nie na oko.
- Bez trafień zostaje sam nagłówek.
- Karta i wątek nie występują razem: baza wektorowa trzyma karty, baza tekstowa oryginały,
  a każde narzędzie pokazuje to, co trzyma jego baza.
- Osobnego bloku przyczyn przed rekordami już nie ma (2026-10-03). Powstał pod model 11B, do
  którego przyczyna schowana wśród pól rekordu nie docierała; czy mocny model radzi sobie bez
  niego, sprawdza pomiar w p. 25.
"""

from collections.abc import Sequence

from app.model.ticket_parsed import ParsedTicket

NO_ERROR_CODES = "(brak)"


def render_ticket_record(
    ticket:    ParsedTicket,  # np. ParsedTicket(ticket_id="90001", …)
    how_found: str,           # np. "podobieństwo 0.91" albo "dopasowanie: słowa"
) -> str:
    """
    Description:
    Jeden rekord w tekście dla modelu: linia z id, datą i informacją, jak go znaleziono, pod nią
    pola payloadu pod nazwami ze schematu.

    Example args:
        ticket=ParsedTicket(ticket_id="90001", …)
        how_found="podobieństwo 0.91"

    Example result:
        [90001] 2026-02-10 · podobieństwo 0.91
        component: e-Doręczenia
        problem: Nie przychodzą przesyłki z e-Doręczeń
        …
    """
    lines = [
        f"[{ticket.ticket_id}] {ticket.date.isoformat()} · {how_found}",
        f"component: {ticket.component}",
        f"problem: {ticket.problem}",
        f"symptoms: {ticket.symptoms}",
        f"error_codes: {', '.join(ticket.error_codes) or NO_ERROR_CODES}",
        f"cause: {ticket.cause}",
        f"solution: {ticket.solution}",
        f"resolution: {ticket.resolution}",
        f"questions_summary: {ticket.questions_summary}",
    ]

    return "\n".join(lines)


def render_ticket_thread(
    ticket_id: str,  # np. "90011"
    thread:    str,  # np. "ZGŁOSZENIE 90011 z 2026-03-02\nTemat: Błąd przy podpisie\n…"
) -> str:
    """
    Description:
    Wątek zgłoszenia w tekście dla modelu: treść po anonimizacji między dwiema liniami z numerem
    zgłoszenia. Wątek ma własne puste linie, więc bez ogranicznika nie byłoby widać, gdzie się
    kończy i gdzie zaczyna następny rekord.

    Example args:
        ticket_id="90011"
        thread="ZGŁOSZENIE 90011 z 2026-03-02\nTemat: Błąd przy podpisie\n…"

    Example result:
        --- wątek 90011 ---
        ZGŁOSZENIE 90011 z 2026-03-02
        Temat: Błąd przy podpisie
        …
        --- koniec wątku 90011 ---
    """
    lines = [
        f"--- wątek {ticket_id} ---",
        thread.strip(),
        f"--- koniec wątku {ticket_id} ---",
    ]

    return "\n".join(lines)


def render_found_tickets(
    header:  str,                                 # np. "Znalezione zgłoszenia: 2 (pominięte: 0)"
    entries: Sequence[tuple[ParsedTicket, str]],  # np. [(ParsedTicket(…), "podobieństwo 0.91"), …]
) -> str:
    """
    Description:
    Cały tekst wyniku: nagłówek narzędzia i rekordy. Bez trafień zostaje sam nagłówek.

    Example args:
        header="Znalezione zgłoszenia: 1 (odcięte progiem: 1)"
        entries=[(ParsedTicket(ticket_id="90001", …), "podobieństwo 0.91")]

    Example result:
        Znalezione zgłoszenia: 1 (odcięte progiem: 1)

        [90001] 2026-02-10 · podobieństwo 0.91
        component: e-Doręczenia
        …
    """
    records = [render_ticket_record(ticket, how_found) for ticket, how_found in entries]

    text = "\n\n".join([header, *records])

    return text
