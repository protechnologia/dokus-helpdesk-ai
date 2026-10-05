import pytest
from pydantic import ValidationError

from app.agent_tools.docs.fake_docs import default_sections
from app.core_model.doc_section import DocSection
from app.db_qdrant import DocHit, DocPoint, TicketHit

# Trafienia obu materiałów: odczyt jednego wpisu odpowiedzi wyszukiwania. Bez transportu — same
# modele.

SECTION = default_sections()[0]

# Payload karty zgłoszenia w kształcie, w jakim zapisuje go indeksacja; treść zmyślona.
TICKET_PAYLOAD = {
    "ticket_id":         "33644",
    "date":              "2026-06-23",
    "component":         "ePUAP",
    "problem":           "Brak wizualizacji UPP",
    "symptoms":          "nie dotyczy",
    "error_codes":       "brak",
    "cause":             "brak",
    "solution":          "Wygenerowano podglądy ręcznie.",
    "resolution":        "naprawione",
    "questions_summary": "brak",
    "resolution_vocabulary_version": "1",
}

# Payload sekcji taki, jaki zapisuje `DocPoint`.
SECTION_PAYLOAD = DocPoint.from_fragment(SECTION, 0, [0.1, 0.2]).payload


# --- trafienie zgłoszenia -----------------------------------------------------------------

def test_ticket_hit_reads_a_qdrant_entry() -> None:
    """Wpis odpowiedzi wyszukiwania → trafienie z identyfikatorem, podobieństwem i payloadem
    bez zmian."""
    hit = TicketHit.from_qdrant(
        {"id": "3f2a1c9e", "score": 0.87, "payload": {"ticket_id": "33644", "cause": "brak"}}
    )

    assert hit.point_id  == "3f2a1c9e"
    assert hit.score     == 0.87
    assert hit.ticket_id == "33644"
    assert hit.payload["cause"] == "brak"


def test_ticket_hit_keeps_the_payload_whole() -> None:
    """Każdy klucz payloadu przeżywa odczyt: prompt generacji czyta pola, których ten model nie
    wymienia, więc rozbicie na stały zestaw byłoby drugim miejscem, w którym można któreś zgubić."""
    hit = TicketHit.from_qdrant({"id": "a", "score": 0.5, "payload": TICKET_PAYLOAD})

    assert hit.payload == TICKET_PAYLOAD


def test_ticket_hit_without_a_payload_is_not_an_error() -> None:
    """Punkt zapisany bez payloadu → pusty słownik, nie awaria: to poprawny stan kolekcji."""
    hit = TicketHit.from_qdrant({"id": "a", "score": 0.5, "payload": None})

    assert hit.payload   == {}
    assert hit.ticket_id == ""


def test_ticket_hit_without_a_score_reads_as_zero() -> None:
    """Wpis bez podobieństwa → 0.0, które odrzuci każdy próg: nierozpoznany kształt nie może
    wyprzedzić prawdziwych trafień."""
    hit = TicketHit.from_qdrant({"id": "a"})

    assert hit.score == 0.0


def test_ticket_hit_refuses_an_unknown_field() -> None:
    """Pole spoza kontraktu → `ValidationError`: trafienie nie niesie wektorów, a rozjechany
    kształt to pomyłka, nie rozszerzenie."""
    with pytest.raises(ValidationError):
        TicketHit(point_id="a", score=0.5, payload={}, vector=[0.1])


# --- trafienie dokumentacji ---------------------------------------------------------------

def test_doc_hit_reads_a_qdrant_entry() -> None:
    """Wpis odpowiedzi wyszukiwania → trafienie we fragment: podobieństwo i opis jego sekcji
    z payloadu."""
    hit = DocHit.from_qdrant({"id": "a", "score": 0.74, "payload": SECTION_PAYLOAD})

    assert hit.point_id   == "a"
    assert hit.score      == 0.74
    assert hit.section_id == SECTION.section_id
    assert hit.payload    == SECTION_PAYLOAD


def test_doc_hit_payload_reads_back_as_the_section() -> None:
    """Payload trafienia → z powrotem ta sama `DocSection`: tak `find_docs_vector` zbuduje
    wiersz spisu."""
    hit = DocHit.from_qdrant({"id": "a", "score": 0.74, "payload": SECTION_PAYLOAD})

    assert DocSection.model_validate(hit.payload) == SECTION


def test_doc_hit_without_score_or_payload_reads_as_empty() -> None:
    """Wpis bez podobieństwa i payloadu → 0.0 i pusty słownik, nie awaria."""
    hit = DocHit.from_qdrant({"id": "a"})

    assert hit.score      == 0.0
    assert hit.payload    == {}
    assert hit.section_id == ""


def test_doc_hit_refuses_an_unknown_field() -> None:
    """Pole spoza kontraktu → `ValidationError`, jak w trafieniu zgłoszenia."""
    with pytest.raises(ValidationError):
        DocHit(point_id="a", score=0.5, payload={}, vector=[0.1])
