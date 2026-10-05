from datetime import date

import pytest

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.tickets.fake_tickets import SIGNING_THREAD
from app.db_postgres import DocRow, TicketRow


def test_a_ticket_row_is_built_from_its_thread() -> None:
    """Sprawdza, czy wiersz zgłoszenia zbudowany z numeru, daty i tekstu wątku ma temat wycięty
    z linii „Temat:" tego wątku („Błąd przy podpisie") i cały wątek bez zmian.

    Wyłapuje budowanie wiersza, które gubi albo przekręca temat lub zmienia tekst wątku. Do bazy
    trafia tylko tekst po anonimizacji, więc temat musi pochodzić z wątku, a nie ze źródła sprzed
    anonimizacji."""
    row = TicketRow.from_thread("90011", date(2026, 3, 2), SIGNING_THREAD)

    assert row.subject == "Błąd przy podpisie"
    assert row.thread  == SIGNING_THREAD


def test_a_text_that_is_not_a_thread_gives_no_row() -> None:
    """Sprawdza, czy próba zbudowania wiersza zgłoszenia z tekstu, w którym nie ma linii z tematem,
    kończy się wyjątkiem `ValueError`.

    Wyłapuje budowanie wiersza, które przy braku tematu wstawia coś zastępczego: taki wiersz
    wyglądałby w bazie na poprawny, choć nie ma tytułu, po którym człowiek rozpozna zgłoszenie."""
    with pytest.raises(ValueError):
        TicketRow.from_thread("90011", date(2026, 3, 2), "Dzień dobry, nie działa podpis.")


def test_a_section_survives_the_trip_through_its_row() -> None:
    """Sprawdza, czy opis sekcji dokumentacji zamieniony na wiersz tabeli i odtworzony z niego
    z powrotem jest taki sam jak na początku, a wiersz niesie przy tym miejsce sekcji w dokumencie
    i ścieżkę rozdziału zapisaną jako lista w JSON-ie.

    Wyłapuje przekształcenie, które po drodze gubi albo zmienia któreś pole opisu, na przykład
    ścieżkę rozdziału: agent dostałby wtedy z bazy inny opis sekcji niż ten z plików
    dokumentacji."""
    section = default_sections()[0]

    row = DocRow.from_section(section, body="Uprawnienie nadaje administrator.", ordinal=3)

    assert row.to_section() == section
    assert row.ordinal      == 3
    assert row.chapter_path == '["Uprawnienia", "Kancelaria"]'
