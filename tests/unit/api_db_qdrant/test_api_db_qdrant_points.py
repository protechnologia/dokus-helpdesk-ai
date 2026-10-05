import uuid

import pytest
from pydantic import ValidationError

from app.agent_tools.docs.fake_docs import default_sections
from app.core_model.doc_section import DocSection
from app.core_model.ticket_parsed import ParsedTicket
from app.db_qdrant import (
    VECTOR_PROBLEM,
    VECTOR_SECTION,
    VECTOR_STS,
    DbQdrantConfigError,
    DocPoint,
    TicketPoint,
    point_id_for,
)

# Punkty obu materiałów: przejście z modelu dziedziny na to, co trzyma Qdrant, a dla zgłoszeń
# także z powrotem, z tego, co Qdrant oddaje przy odczycie po identyfikatorze. Bez transportu —
# same modele.

# Ten sam rekord wyjściowy, od którego odchodzą testy `ParsedTicket`, żeby zmiana schematu
# psuła oba pliki tak samo.
VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "Certyfikat bez uprawnienia AddDocumentToSign",
    "solution":                      "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "pytano o wersję przeglądarki",
}

SECTION = default_sections()[0]

# Dwa rozróżnialne wektory: asercja ma umieć powiedzieć, KTÓRY trafił w które miejsce.
VECTOR_A = [0.1, -0.2, 0.3]
VECTOR_B = [0.9, 0.8, -0.7]


def _ticket_point(
    **overrides: object,  # np. ticket_id="33645"
) -> TicketPoint:
    """
    Description:
    Buduje punkt z poprawnej karty zgłoszenia, z podmienionymi polami.

    Example args:
        ticket_id="33645"

    Example result:
        TicketPoint(point_id="…", payload={"ticket_id": "33645", …})
    """
    ticket = ParsedTicket(**{**VALID_TICKET, **overrides})
    point  = TicketPoint.from_ticket(
        ticket         = ticket,
        vector_problem = VECTOR_A,
        vector_sts     = VECTOR_B,
    )

    return point


# --- identyfikator punktu -----------------------------------------------------------------

def test_point_id_is_a_uuid() -> None:
    """Identyfikator źródłowy (tekst w rodzaju „33644") → UUID, jedyny kształt, jaki przyjmuje
    Qdrant."""
    # Asercją jest samo parsowanie: uuid.UUID() odrzuca wszystko, co nim nie jest.
    assert uuid.UUID(point_id_for("33644"))


def test_point_id_is_stable_across_calls() -> None:
    """Ten sam identyfikator dwa razy → ten sam punkt; dzięki temu przebudowa nadpisuje, a nie
    dubluje korpus."""
    assert point_id_for("33644") == point_id_for("33644")


def test_point_id_is_a_golden_value() -> None:
    """Znany identyfikator → dokładnie ten UUID. Pilnuje zamrożonego namespace'u: jego zmiana
    rozsypuje wszystkie identyfikatory, a następna przebudowa dubluje korpus — nic innego
    w zestawie tego nie zauważy."""
    assert point_id_for("33644") == "df3b51f3-9eac-56f3-9f28-6253f23dd731"


def test_different_sources_get_different_ids() -> None:
    """Dwa identyfikatory → dwa punkty (kolizja po cichu zgubiłaby jeden rekord)."""
    assert point_id_for("33644") != point_id_for("33645")


# --- punkt zgłoszenia ---------------------------------------------------------------------

def test_ticket_payload_carries_every_card_field() -> None:
    """Karta zgłoszenia → payload ze wszystkim, co czyta prompt generacji."""
    payload = _ticket_point().payload

    # Wymienione po kolei, a nie porównane jako zbiór: ta lista JEST kontraktem z promptem
    # generacji, więc pole zgubione w payloadzie ma paść tutaj.
    assert payload["ticket_id"]         == "33644"
    assert payload["component"]         == "ePUAP"
    assert payload["problem"]           == VALID_TICKET["problem"]
    assert payload["symptoms"]          == VALID_TICKET["symptoms"]
    assert payload["error_codes"]       == ["ERR-4210"]
    assert payload["cause"]             == VALID_TICKET["cause"]
    assert payload["solution"]          == VALID_TICKET["solution"]
    assert payload["resolution"]        == "naprawione"
    assert payload["questions_summary"] == VALID_TICKET["questions_summary"]
    assert payload["resolution_vocabulary_version"] == 1


def test_ticket_payload_date_is_an_iso_string() -> None:
    """Data → tekst ISO, nie obiekt daty: JSON nie ma typu daty, a Qdrant sortuje takie teksty
    poprawnie."""
    assert _ticket_point().payload["date"] == "2026-03-14"


def test_ticket_payload_reads_back_as_the_same_card() -> None:
    """Payload punktu → z powrotem ta sama `ParsedTicket`: tak narzędzie odtwarza kartę
    z trafienia."""
    assert ParsedTicket.model_validate(_ticket_point().payload) == ParsedTicket(**VALID_TICKET)


def test_ticket_wire_shape_names_both_vectors() -> None:
    """`to_qdrant()` → wektory pod NAZWAMI, każdy na swoim miejscu. Zamieniona para wstawiłaby
    zapytania i porównania w cudze przestrzenie — niewidocznie, bo obie dalej wyglądają dobrze."""
    vectors = _ticket_point().to_qdrant()["vector"]

    assert vectors[VECTOR_PROBLEM] == VECTOR_A
    assert vectors[VECTOR_STS]     == VECTOR_B


def test_ticket_wire_shape_carries_id_and_payload() -> None:
    """`to_qdrant()` → trzy klucze, których oczekuje zapis Qdranta, z identyfikatorem punktu."""
    wire = _ticket_point().to_qdrant()

    assert set(wire)  == {"id", "vector", "payload"}
    assert wire["id"] == point_id_for("33644")
    assert wire["payload"]["ticket_id"] == "33644"


def test_ticket_point_reads_back_from_its_own_wire_shape() -> None:
    """Punkt zapisany i odczytany po identyfikatorze → ten sam punkt: w tym kształcie wchodzi
    do kolekcji i z niej wraca."""
    point = _ticket_point()

    assert TicketPoint.from_qdrant(point.to_qdrant()) == point
    assert point.ticket_id == "33644"


@pytest.mark.parametrize(
    "vector",
    [
        pytest.param({VECTOR_PROBLEM: VECTOR_A}, id="brak-sts"),
        pytest.param(VECTOR_A, id="wektor-bez-nazwy"),
        pytest.param(None, id="bez-wektorow"),
    ],
)
def test_ticket_point_without_a_named_vector_is_a_config_error(vector: object) -> None:
    """Odczytany punkt bez któregoś nazwanego wektora → błąd konfiguracji: kolekcję zbudowano
    w innym układzie i czekanie tego nie naprawi."""
    entry = {"id": "a", "vector": vector, "payload": {"ticket_id": "33644"}}

    with pytest.raises(DbQdrantConfigError, match="wektora"):
        TicketPoint.from_qdrant(entry)


def test_ticket_point_refuses_an_unknown_field() -> None:
    """Pole spoza kontraktu → `ValidationError`: rozjechany kształt to pomyłka, nie
    rozszerzenie."""
    with pytest.raises(ValidationError):
        TicketPoint(point_id="a", vector_problem=[0.1], vector_sts=[0.1], payload={}, score=0.5)


# --- punkt dokumentacji -------------------------------------------------------------------

def test_doc_point_id_comes_from_the_section_and_the_fragment() -> None:
    """Fragment sekcji → punkt o identyfikatorze wyliczonym z `section_id` i numeru fragmentu,
    a sam `section_id` zostaje w payloadzie: po nim trafienie wskazuje sekcję."""
    point = DocPoint.from_fragment(SECTION, 0, VECTOR_A)

    assert point.point_id   == point_id_for(f"{SECTION.section_id}#0")
    assert point.section_id == SECTION.section_id


def test_fragments_of_one_section_are_different_points() -> None:
    """Dwa fragmenty tej samej sekcji → dwa różne punkty z tym samym opisem sekcji; inaczej
    drugi nadpisałby pierwszy."""
    first  = DocPoint.from_fragment(SECTION, 0, VECTOR_A)
    second = DocPoint.from_fragment(SECTION, 1, VECTOR_B)

    assert first.point_id != second.point_id
    assert first.payload  == second.payload


def test_doc_payload_reads_back_as_the_same_section() -> None:
    """Payload punktu → z powrotem ta sama `DocSection`, z datą i ścieżką rozdziału: tak
    `find_docs_vector` odtworzy wiersz spisu."""
    payload = DocPoint.from_fragment(SECTION, 0, VECTOR_A).payload

    assert payload["date"]         == SECTION.date.isoformat()
    assert payload["chapter_path"] == SECTION.chapter_path
    assert DocSection.model_validate(payload) == SECTION


def test_doc_payload_carries_no_body() -> None:
    """Payload fragmentu → same pola opisu sekcji z metryczki; treść leży w Postgresie."""
    payload = DocPoint.from_fragment(SECTION, 0, VECTOR_A).payload

    assert set(payload) == set(DocSection.model_fields)


def test_doc_wire_shape_names_its_vector() -> None:
    """`to_qdrant()` → wektor pod nazwą `section`, choć jest jeden: goły wektor trafiłby do
    kolekcji bez nazwanych przestrzeni."""
    wire = DocPoint.from_fragment(SECTION, 0, VECTOR_A).to_qdrant()

    assert set(wire)      == {"id", "vector", "payload"}
    assert wire["vector"] == {VECTOR_SECTION: VECTOR_A}
