from app.db import DocRow, TicketRow
from app.tools.docs.fake_docs import default_sections
from app.tools.tickets.find_tickets_vector.fake import default_tickets


def test_a_ticket_survives_the_trip_through_its_row() -> None:
    """Zgłoszenie → wiersz → zgłoszenie: bez zmian, a wątek jedzie obok w swoim polu."""
    ticket = default_tickets()[0].ticket

    row = TicketRow.from_ticket(ticket, thread="Dzień dobry, od wczoraj nie przychodzą przesyłki.")

    assert row.to_ticket() == ticket
    assert row.thread.startswith("Dzień dobry")


def test_error_codes_are_one_text_with_a_code_per_line() -> None:
    """Lista kodów → jeden tekst, po kodzie na linię, i z powrotem lista; brak kodów to pusty
    tekst, a nie lista z jednym pustym kodem."""
    plain  = default_tickets()[0].ticket
    ticket = plain.model_copy(update={"error_codes": ["ERR-4210", "ORA-00942"]})

    with_codes    = TicketRow.from_ticket(ticket, thread="wątek")
    without_codes = TicketRow.from_ticket(plain, thread="wątek")

    assert with_codes.error_codes                == "ERR-4210\nORA-00942"
    assert with_codes.to_ticket().error_codes    == ["ERR-4210", "ORA-00942"]
    assert without_codes.error_codes             == ""
    assert without_codes.to_ticket().error_codes == []


def test_a_section_survives_the_trip_through_its_row() -> None:
    """Opis sekcji → wiersz → opis sekcji: bez zmian; treść i kolejność jadą w swoich polach."""
    section = default_sections()[0]

    row = DocRow.from_section(section, body="Uprawnienie nadaje administrator.", ordinal=3)

    assert row.to_section() == section
    assert row.ordinal      == 3
    assert row.chapter_path == '["Uprawnienia", "Kancelaria"]'
