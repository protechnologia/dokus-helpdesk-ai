from datetime import date

import pytest

from app.db import DocRow, TicketRow
from app.tools.docs.fake_docs import default_sections
from app.tools.tickets.find_tickets_text.fake import SIGNING_THREAD


def test_a_ticket_row_is_built_from_its_thread() -> None:
    """Numer, data i wątek → wiersz z tematem wyciętym z wątku: do bazy trafia tylko tekst po
    anonimizacji, więc temat nie przychodzi ze źródła."""
    row = TicketRow.from_thread("90011", date(2026, 3, 2), SIGNING_THREAD)

    assert row.subject == "Błąd przy podpisie"
    assert row.thread  == SIGNING_THREAD


def test_a_text_that_is_not_a_thread_gives_no_row() -> None:
    """Tekst bez linii z tematem → ValueError: wiersz bez tytułu wyglądałby na poprawny."""
    with pytest.raises(ValueError):
        TicketRow.from_thread("90011", date(2026, 3, 2), "Dzień dobry, nie działa podpis.")


def test_a_section_survives_the_trip_through_its_row() -> None:
    """Opis sekcji → wiersz → opis sekcji: bez zmian; treść i kolejność jadą w swoich polach."""
    section = default_sections()[0]

    row = DocRow.from_section(section, body="Uprawnienie nadaje administrator.", ordinal=3)

    assert row.to_section() == section
    assert row.ordinal      == 3
    assert row.chapter_path == '["Uprawnienia", "Kancelaria"]'
