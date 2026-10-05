import uuid

import pytest
from pydantic import ValidationError

from app.agent_tools.docs.fake_docs import default_sections
from app.core_model.docs.doc_section import DocSection
from app.core_model.tickets.parsed_ticket import ParsedTicket
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
    """Sprawdza, czy identyfikator punktu wyliczony z numeru zgłoszenia „33644" jest poprawnym UUID.

    Wyłapuje identyfikator w innej postaci: Qdrant przyjmuje jako identyfikator punktu tylko liczbę
    albo UUID, więc odrzucałby każdy zapisywany punkt."""
    # Asercją jest samo parsowanie: uuid.UUID() odrzuca wszystko, co nim nie jest.
    assert uuid.UUID(point_id_for("33644"))


def test_point_id_is_stable_across_calls() -> None:
    """Sprawdza, czy ten sam numer zgłoszenia daje przy dwóch wywołaniach ten sam identyfikator
    punktu.

    Wyłapuje identyfikator, który zależy od czegoś poza numerem, np. od losowości: ponowna
    indeksacja nie trafiałaby w te same punkty i dublowałaby korpus, zamiast go nadpisać."""
    assert point_id_for("33644") == point_id_for("33644")


def test_point_id_is_a_golden_value() -> None:
    """Sprawdza, czy numer zgłoszenia „33644" daje dokładnie ten identyfikator punktu, który
    zapisano w teście (`df3b51f3-9eac-56f3-9f28-6253f23dd731`).

    Wyłapuje zmianę stałej, z której liczone są identyfikatory (namespace UUID): wszystkie punkty
    dostałyby nowe identyfikatory, a następna indeksacja zdublowałaby korpus, zamiast go nadpisać.
    Żaden inny test tego nie zauważy."""
    assert point_id_for("33644") == "df3b51f3-9eac-56f3-9f28-6253f23dd731"


def test_different_sources_get_different_ids() -> None:
    """Sprawdza, czy dwa różne numery zgłoszeń („33644" i „33645") dają różne identyfikatory
    punktów.

    Wyłapuje wyliczanie, które różnym zgłoszeniom daje ten sam identyfikator: jedno nadpisałoby
    drugie i rekord zniknąłby z indeksu po cichu."""
    assert point_id_for("33644") != point_id_for("33645")


# --- punkt zgłoszenia ---------------------------------------------------------------------

def test_ticket_payload_carries_every_card_field() -> None:
    """Sprawdza, czy punkt zbudowany z karty zgłoszenia niesie w danych (payload) dziesięć pól
    karty, od numeru zgłoszenia po wersję słownika rozstrzygnięć, każde z wartością z karty.

    Wyłapuje pole zgubione albo przekręcone przy budowie punktu: z tych pól korzysta prompt
    generacji, więc brakujące znikałoby z odpowiedzi po cichu."""
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
    """Sprawdza, czy data zgłoszenia trafia do danych punktu jako tekst w formacie ISO
    („2026-03-14"), a nie jako obiekt daty.

    Wyłapuje datę zapisaną w innej postaci: JSON nie ma typu daty, a teksty w formacie ISO Qdrant
    sortuje poprawnie."""
    assert _ticket_point().payload["date"] == "2026-03-14"


def test_ticket_payload_reads_back_as_the_same_card() -> None:
    """Sprawdza, czy z danych punktu da się odtworzyć dokładnie tę samą kartę zgłoszenia
    (`ParsedTicket`), z której punkt zbudowano.

    Wyłapuje dane punktu, które przestały pasować do karty, np. po dopisaniu do niej pola: narzędzie
    agenta odtwarza kartę właśnie z nich, więc odczyt zgłoszenia kończyłby się błędem albo inną
    kartą."""
    assert ParsedTicket.model_validate(_ticket_point().payload) == ParsedTicket(**VALID_TICKET)


def test_ticket_wire_shape_names_both_vectors() -> None:
    """Sprawdza, czy `to_qdrant()` oddaje oba wektory zgłoszenia pod nazwami i każdy na swoim
    miejscu: wektor problemu pod `problem`, a wektor porównań pod `sts`.

    Wyłapuje zamienioną parę wektorów: zapytania trafiałyby wtedy w niewłaściwą przestrzeń i nic by
    tego nie zgłosiło, bo obie przestrzenie dalej oddają wiarygodnie wyglądające wyniki."""
    vectors = _ticket_point().to_qdrant()["vector"]

    assert vectors[VECTOR_PROBLEM] == VECTOR_A
    assert vectors[VECTOR_STS]     == VECTOR_B


def test_ticket_wire_shape_carries_id_and_payload() -> None:
    """Sprawdza, czy `to_qdrant()` oddaje punkt zgłoszenia z dokładnie trzema kluczami, których
    oczekuje zapis Qdranta (`id`, `vector`, `payload`), z identyfikatorem wyliczonym z numeru
    zgłoszenia i z danymi karty.

    Wyłapuje punkt wysłany w innym kształcie albo pod innym identyfikatorem: zapis by się nie
    powiódł albo zgłoszenia nie dałoby się potem odczytać po numerze."""
    wire = _ticket_point().to_qdrant()

    assert set(wire)  == {"id", "vector", "payload"}
    assert wire["id"] == point_id_for("33644")
    assert wire["payload"]["ticket_id"] == "33644"


def test_ticket_point_reads_back_from_its_own_wire_shape() -> None:
    """Sprawdza, czy punkt zgłoszenia zamieniony na kształt zapisu Qdranta i odczytany z powrotem
    jest tym samym punktem i oddaje swój numer zgłoszenia.

    Wyłapuje zapis i odczyt, które przestały do siebie pasować: zgłoszenie wchodzi do kolekcji
    i wraca z niej w tym samym kształcie, więc odczyt po numerze oddawałby inny punkt, niż
    zapisano."""
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
    """Sprawdza, czy odczyt punktu, któremu brakuje nazwanego wektora, kończy się błędem
    konfiguracji (`DbQdrantConfigError`) mówiącym o wektorze. Trzy przypadki: punkt z samym wektorem
    `problem`, punkt z jednym wektorem bez nazwy i punkt bez wektorów.

    Wyłapuje odczyt, który taki punkt przyjmuje albo pada niejasnym wyjątkiem: brak wektora znaczy,
    że kolekcję zbudowano w innym układzie, i czekanie tego nie naprawi."""
    entry = {"id": "a", "vector": vector, "payload": {"ticket_id": "33644"}}

    with pytest.raises(DbQdrantConfigError, match="wektora"):
        TicketPoint.from_qdrant(entry)


def test_ticket_point_refuses_an_unknown_field() -> None:
    """Sprawdza, czy punkt zgłoszenia zbudowany z polem spoza modelu (tutaj `score`) kończy się
    błędem `ValidationError`.

    Wyłapuje model, który po cichu przyjmuje albo pomija nieznane pola: dodatkowe pole to pomyłka
    w kształcie danych, której nikt by nie zauważył."""
    with pytest.raises(ValidationError):
        TicketPoint(point_id="a", vector_problem=[0.1], vector_sts=[0.1], payload={}, score=0.5)


# --- punkt dokumentacji -------------------------------------------------------------------

def test_doc_point_id_comes_from_the_section_and_the_fragment() -> None:
    """Sprawdza, czy punkt fragmentu sekcji dostaje identyfikator wyliczony z identyfikatora sekcji
    i numeru fragmentu (tutaj fragment 0), a sam identyfikator sekcji zostaje w danych punktu.

    Wyłapuje identyfikator punktu liczony inaczej, po którym ponowna indeksacja nie trafia w te same
    punkty, oraz punkt bez identyfikatora sekcji: trafienie nie miałoby czym wskazać sekcji."""
    point = DocPoint.from_fragment(SECTION, 0, VECTOR_A)

    assert point.point_id   == point_id_for(f"{SECTION.section_id}#0")
    assert point.section_id == SECTION.section_id


def test_fragments_of_one_section_are_different_points() -> None:
    """Sprawdza, czy dwa fragmenty tej samej sekcji dają dwa punkty o różnych identyfikatorach
    i z tym samym opisem sekcji.

    Wyłapuje identyfikator punktu, który pomija numer fragmentu: drugi fragment nadpisałby pierwszy
    i z długiej sekcji zostałby w indeksie tylko ostatni."""
    first  = DocPoint.from_fragment(SECTION, 0, VECTOR_A)
    second = DocPoint.from_fragment(SECTION, 1, VECTOR_B)

    assert first.point_id != second.point_id
    assert first.payload  == second.payload


def test_doc_payload_reads_back_as_the_same_section() -> None:
    """Sprawdza, czy dane punktu dokumentacji niosą datę jako tekst ISO i ścieżkę rozdziału oraz czy
    da się z nich odtworzyć ten sam opis sekcji (`DocSection`).

    Wyłapuje dane punktu, które przestały pasować do opisu sekcji: narzędzie `find_docs_vector`
    odtwarza z nich pozycję wyniku, więc wyszukiwanie w dokumentacji kończyłoby się błędem albo
    innym opisem."""
    payload = DocPoint.from_fragment(SECTION, 0, VECTOR_A).payload

    assert payload["date"]         == SECTION.date.isoformat()
    assert payload["chapter_path"] == SECTION.chapter_path
    assert DocSection.model_validate(payload) == SECTION


def test_doc_payload_carries_no_body() -> None:
    """Sprawdza, czy dane punktu dokumentacji mają dokładnie te pola, które ma opis sekcji
    (`DocSection`), i żadnego więcej.

    Wyłapuje treść sekcji albo fragmentu dopisaną do punktu oraz zgubione pole opisu: treść leży
    w Postgresie, a punkt ma nieść tylko opis sekcji."""
    payload = DocPoint.from_fragment(SECTION, 0, VECTOR_A).payload

    assert set(payload) == set(DocSection.model_fields)


def test_doc_wire_shape_names_its_vector() -> None:
    """Sprawdza, czy `to_qdrant()` oddaje punkt dokumentacji z trzema kluczami (`id`, `vector`,
    `payload`) i z wektorem pod nazwą `section`, choć wektor jest tylko jeden.

    Wyłapuje wektor wysłany bez nazwy: taki pasuje do kolekcji bez nazwanych wektorów, a kolekcja
    dokumentacji je ma."""
    wire = DocPoint.from_fragment(SECTION, 0, VECTOR_A).to_qdrant()

    assert set(wire)      == {"id", "vector", "payload"}
    assert wire["vector"] == {VECTOR_SECTION: VECTOR_A}
