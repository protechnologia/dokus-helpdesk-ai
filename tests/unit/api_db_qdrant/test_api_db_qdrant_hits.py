import pytest
from pydantic import ValidationError

from app.agent_tools.docs.fake_docs import default_sections
from app.core_model.docs.doc_section import DocSection
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
    """Sprawdza, czy z jednego wpisu odpowiedzi wyszukiwania powstaje trafienie zgłoszenia
    (`TicketHit`) z identyfikatorem punktu, podobieństwem i numerem zgłoszenia, a dane karty
    (payload) zostają bez zmian.

    Wyłapuje odczyt wpisu, który gubi albo myli któreś z tych pól: na trafieniu, a nie na odpowiedzi
    Qdranta, pracuje dalej próg podobieństwa i narzędzie agenta."""
    hit = TicketHit.from_qdrant(
        {"id": "3f2a1c9e", "score": 0.87, "payload": {"ticket_id": "33644", "cause": "brak"}}
    )

    assert hit.point_id  == "3f2a1c9e"
    assert hit.score     == 0.87
    assert hit.ticket_id == "33644"
    assert hit.payload["cause"] == "brak"


def test_ticket_hit_keeps_the_payload_whole() -> None:
    """Sprawdza, czy trafienie zgłoszenia oddaje dane karty w całości: wszystkie 11 pól przykładowej
    karty wraca bez zmian.

    Wyłapuje odczyt, który przepisuje tylko wybrane pola: prompt generacji czyta także te, których
    model trafienia nie wymienia, więc pole zgubione tutaj znikałoby z odpowiedzi po cichu."""
    hit = TicketHit.from_qdrant({"id": "a", "score": 0.5, "payload": TICKET_PAYLOAD})

    assert hit.payload == TICKET_PAYLOAD


def test_ticket_hit_without_a_payload_is_not_an_error() -> None:
    """Sprawdza, czy wpis bez danych karty (`payload` równe `None`) daje trafienie z pustym
    słownikiem i pustym numerem zgłoszenia, bez wyjątku.

    Wyłapuje odczyt, który na takim wpisie pada: punkt zapisany bez danych to poprawny stan
    kolekcji, a jeden taki punkt wywracałby całe wyszukiwanie."""
    hit = TicketHit.from_qdrant({"id": "a", "score": 0.5, "payload": None})

    assert hit.payload   == {}
    assert hit.ticket_id == ""


def test_ticket_hit_without_a_score_reads_as_zero() -> None:
    """Sprawdza, czy wpis bez podobieństwa daje trafienie z podobieństwem 0.0.

    Wyłapuje odczyt, który na takim wpisie pada albo nadaje mu inną wartość: zero odrzuci każdy
    próg, więc wpis w nierozpoznanym kształcie nie wyprzedzi prawdziwych trafień."""
    hit = TicketHit.from_qdrant({"id": "a"})

    assert hit.score == 0.0


def test_ticket_hit_refuses_an_unknown_field() -> None:
    """Sprawdza, czy trafienie zgłoszenia zbudowane z polem spoza modelu (tutaj `vector`) kończy się
    błędem `ValidationError`.

    Wyłapuje model, który po cichu przyjmuje albo pomija nieznane pola: trafienie nie niesie
    wektorów, a dodatkowe pole to pomyłka w kształcie danych, której nikt by nie zauważył."""
    with pytest.raises(ValidationError):
        TicketHit(point_id="a", score=0.5, payload={}, vector=[0.1])


# --- trafienie dokumentacji ---------------------------------------------------------------

def test_doc_hit_reads_a_qdrant_entry() -> None:
    """Sprawdza, czy z jednego wpisu odpowiedzi wyszukiwania powstaje trafienie w dokumentacji
    (`DocHit`) z identyfikatorem punktu, podobieństwem i identyfikatorem sekcji, a opis sekcji
    (payload) zostaje bez zmian.

    Wyłapuje odczyt wpisu, który gubi albo myli któreś z tych pól: po identyfikatorze sekcji
    trafienie wskazuje, którą sekcję znaleziono, a z opisu powstaje wynik dla agenta."""
    hit = DocHit.from_qdrant({"id": "a", "score": 0.74, "payload": SECTION_PAYLOAD})

    assert hit.point_id   == "a"
    assert hit.score      == 0.74
    assert hit.section_id == SECTION.section_id
    assert hit.payload    == SECTION_PAYLOAD


def test_doc_hit_payload_reads_back_as_the_section() -> None:
    """Sprawdza, czy z danych trafienia w dokumentacji da się odtworzyć ten sam opis sekcji
    (`DocSection`), z którego zbudowano zapisany punkt.

    Wyłapuje opis sekcji, który zmienia się między zapisem punktu a odczytem trafienia: narzędzie
    `find_docs_vector` buduje z niego pozycję wyniku, więc agent dostałby inny opis albo błąd."""
    hit = DocHit.from_qdrant({"id": "a", "score": 0.74, "payload": SECTION_PAYLOAD})

    assert DocSection.model_validate(hit.payload) == SECTION


def test_doc_hit_without_score_or_payload_reads_as_empty() -> None:
    """Sprawdza, czy wpis bez podobieństwa i bez opisu sekcji daje trafienie z podobieństwem 0.0,
    pustym słownikiem i pustym identyfikatorem sekcji, bez wyjątku.

    Wyłapuje odczyt, który na niepełnym wpisie pada: jeden taki wpis wywracałby całe wyszukiwanie
    w dokumentacji, zamiast odpaść na progu podobieństwa."""
    hit = DocHit.from_qdrant({"id": "a"})

    assert hit.score      == 0.0
    assert hit.payload    == {}
    assert hit.section_id == ""


def test_doc_hit_refuses_an_unknown_field() -> None:
    """Sprawdza, czy trafienie w dokumentacji zbudowane z polem spoza modelu (tutaj `vector`) kończy
    się błędem `ValidationError`, tak jak trafienie zgłoszenia.

    Wyłapuje model, który po cichu przyjmuje albo pomija nieznane pola: dodatkowe pole to pomyłka
    w kształcie danych, której nikt by nie zauważył."""
    with pytest.raises(ValidationError):
        DocHit(point_id="a", score=0.5, payload={}, vector=[0.1])
