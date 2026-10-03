from datetime import date

import pytest

from app.model.ticket_parsed import ParsedTicket
from app.tools.find_tickets_vector import (
    FakeFindTicketsVector,
    FindTicketsVectorResult,
    FoundTicket,
)
from app.tools.find_tickets_vector.base import CAUSE_NOT_ESTABLISHED, CAUSES_HEADING

# Tekst dla modelu i lista źródeł są wspólne dla narzędzia i atrapy (`FindTicketsVectorBase`), więc
# sprawdzamy je na atrapie z produkcji — bez embeddera i Qdranta.


def _found(
    ticket_id: str,                # np. "90001"
    cause:     str,                # np. "Zacięta kolejka pobierania"
    score:     float     = 0.9,    # np. 0.91
    codes:     list[str] = (),     # np. ["ERR-4210"]
) -> FoundTicket:
    """
    Description:
    Jedno zmyślone trafienie; testy różnią się tylko id, przyczyną i kodami błędów.

    Example args:
        ticket_id="90001"
        cause="Zacięta kolejka pobierania"

    Example result:
        FoundTicket(score=0.9, ticket=ParsedTicket(ticket_id="90001", cause="Zacięta…", …))
    """
    ticket = ParsedTicket(
        ticket_id                     = ticket_id,
        date                          = date(2026, 2, 10),
        component                     = "e-Doręczenia",
        problem                       = "Nie przychodzą przesyłki z e-Doręczeń",
        symptoms                      = "Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę",
        error_codes                   = list(codes),
        cause                         = cause,
        solution                      = "Zrestartowano kolejkę; zaległe przesyłki pobrały się.",
        resolution                    = "naprawione",
        resolution_vocabulary_version = 1,
        questions_summary             = "pytano, od kiedy brak przesyłek",
    )

    found = FoundTicket(
        score  = score,
        ticket = ticket,
    )

    return found


def _render(
    *items: FoundTicket,  # np. _found("90001", "Zacięta kolejka pobierania")
) -> str:
    """
    Description:
    Tekst dla modelu z podanych trafień.

    Example args:
        items=(_found("90001", "Zacięta kolejka pobierania"),)

    Example result:
        "Znalezione zgłoszenia: 1 (odcięte progiem: 0)\\n\\nPrzyczyny (`cause`) w trafieniach:…"
    """
    result = FindTicketsVectorResult(items=list(items))
    text   = FakeFindTicketsVector().render_for_model(result)

    return text


def test_the_causes_block_comes_before_the_records() -> None:
    """Dwa trafienia → blok przyczyn stoi przed pierwszym rekordem i ma po linii na trafienie:
    przyczyna utopiona w polach rekordu do modelu nie dociera."""
    text = _render(
        _found("90001", "Zacięta kolejka pobierania"),
        _found("90002", "Plik blokady po aktualizacji"),
    )

    assert text.index(CAUSES_HEADING) < text.index("[90001] 2026-02-10")
    assert "- [90001] Zacięta kolejka pobierania\n- [90002] Plik blokady po aktualizacji" in text


def test_unknown_causes_are_not_shown_as_agreeing() -> None:
    """Trzy trafienia bez ustalonej przyczyny → trzy razy „(nie ustalono)" w bloku, a rekord
    zachowuje oryginalne brzmienie: trzy puste przyczyny to nie trzy zgodne."""
    text = _render(
        _found("90001", "brak"),
        _found("90002", "Brak ustalonej przyczyny w wątku."),
        _found("90003", "brak"),
    )

    block = text.split("\n\n")[1]

    assert block.count(CAUSE_NOT_ESTABLISHED) == 3
    assert "cause: Brak ustalonej przyczyny w wątku." in text


@pytest.mark.parametrize("field", [
    "component",
    "problem",
    "symptoms",
    "error_codes",
    "cause",
    "solution",
    "resolution",
    "questions_summary",
])
def test_a_record_carries_every_payload_field_under_its_schema_name(field: str) -> None:
    """Rekord → każde pole payloadu pod nazwą ze schematu: prompty grafów odwołują się do pól po
    nazwie (`cause`, `solution`, `questions_summary`)."""
    text = _render(_found("90001", "Zacięta kolejka pobierania", codes=["ERR-4210"]))

    assert f"\n{field}: " in text


def test_error_codes_are_joined_and_their_absence_is_said_out_loud() -> None:
    """Kody błędów → po przecinku; pusta lista → „(brak)", a nie pusta linia."""
    with_codes    = _render(_found("90001", "Kolejka", codes=["ERR-4210", "SQLSTATE 23000"]))
    without_codes = _render(_found("90001", "Kolejka"))

    assert "error_codes: ERR-4210, SQLSTATE 23000" in with_codes
    assert "error_codes: (brak)" in without_codes


def test_an_empty_result_is_the_header_alone() -> None:
    """Brak trafień → sam nagłówek z licznikami, bez pustego bloku przyczyn."""
    tool = FakeFindTicketsVector()
    text = tool.render_for_model(FindTicketsVectorResult(items=[], dropped_below_threshold=3))

    assert text == "Znalezione zgłoszenia: 0 (odcięte progiem: 3)"


def test_the_score_and_date_open_each_record() -> None:
    """Rekord → linia z id, datą i podobieństwem: data idzie do modelu bezwarunkowo, bo od niej
    zależą dezaktualizacja i sezonowość."""
    text = _render(_found("90001", "Zacięta kolejka", score=0.912))

    assert "[90001] 2026-02-10 · podobieństwo 0.91" in text
