from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.raw_ticket import RawTicket
from app.core_service.factory_closed_ticket_indexer import ClosedTicketConfigError
from app.core_service.loader_dict_rules import get_rule_set
from app.db_qdrant import DbQdrantError
from app.main import create_app
from tests._helpers.tickets_index import (
    GRAPH_NODES,
    FakeThreads,
    FakeTickets,
    ReplacingAnonymizer,
    app_closing_tickets,
    closed_ticket_indexer_on,
)
from tests._helpers.tickets_index.samples import (
    PERSON,
    PERSON_MARKERS,
    TICKET_ID,
    sample_block,
    sample_card,
    sample_pass,
    sample_raw_ticket,
    sample_request,
    sample_thread,
)

# Kontrakt HTTP `POST /tickets/closed` w procesie: bramka i graf karty to atrapy modelu (karta
# na prawdziwym węźle `respond`), serwis korpusu pisze do katalogu testu, a kolekcja zgłoszeń
# i tabela wątków to atrapy. Co serwis robi z kartą, sprawdzają jego własne testy; tu — co trasa
# mu podaje i co z tego oddaje wołającemu.


def test_a_passed_ticket_is_indexed_and_the_answer_says_so(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie, które bramka przepuszcza, a filtr przyjmuje, trafia do kolekcji
    zgłoszeń i tabeli wątków, a odpowiedź mówi: zaindeksowane, nic nie zastąpiło, werdykt
    „pass” z furtką i wersją reguł bramki zamknięcia, uzasadnienie z karty, zużycie dwóch
    wywołań modelu i log obu grafów po kolei.

    Wyłapuje trasę, która nie dochodzi do zapisu po przepuszczeniu, gubi pole werdyktu albo
    podaje wersję innego zestawu reguł, oraz zużycie i log tylko jednego grafu: wołający nie
    widziałby, ile kosztowało zamknięcie i co się w nim działo."""
    tickets, threads = FakeTickets(), FakeThreads()
    anonymizer       = ReplacingAnonymizer(PERSON, PERSON_MARKERS)
    corpus           = closed_ticket_indexer_on(tmp_path, tickets, threads)
    app              = app_closing_tickets(corpus, sample_pass(), sample_card(), anonymizer)

    response = TestClient(app).post("/tickets/closed", json=sample_request())
    body     = response.json()

    assert response.status_code == 200
    assert [point.ticket_id for point in tickets.points] == [TICKET_ID]
    assert [row.ticket_id for row in threads.rows] == [TICKET_ID]
    assert body["ticket_id"]                      == TICKET_ID
    assert (body["outcome"], body["replaced"])    == ("indexed", False)
    assert (body["verdict"], body["overridable"]) == ("pass", True)
    assert body["rules_version"]                  == get_rule_set("gate_close").version
    assert body["useful_reason"]                  == sample_card().useful_reason
    assert body["dropped_by"]                     == []
    assert body["usage"]["llm_calls"]             == 2
    assert [entry["node"] for entry in body["log"]] == GRAPH_NODES + GRAPH_NODES


def test_the_corpus_gets_the_ticket_its_thread_and_a_card_with_its_identity(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy trasa podaje serwisowi korpusu zgłoszenie z żądania (z osobą, jak przyszło),
    wątek po anonimizacji z grafu karty (osoba zamieniona na znaczniki, a bramka w tym teście
    zostawia ją bez zmian) i kartę z numerem i datą zgłoszenia, dla zgłoszenia 41003, którego
    numeru atrapa modelu nie zna.

    Wyłapuje trasę, która zapisuje jako wątek tekst sprzed anonimizacji — dane osobowe trafiłyby
    do `anonymized/` i do tabeli wątków — albo wątek z grafu bramki, który przy modelu
    anonimizującym może wyjść inaczej niż ten, z którego powstała karta. Wyłapuje też trasę, która
    nie wkłada numeru i daty do stanu grafu karty: karta dostałaby cudzy numer i serwis odmówiłby
    zapisu."""
    ticket_id  = "41003"
    anonymizer = ReplacingAnonymizer(PERSON, PERSON_MARKERS)
    corpus     = closed_ticket_indexer_on(tmp_path, FakeTickets(), FakeThreads())
    app        = app_closing_tickets(corpus, sample_pass(), sample_card(), anonymizer)

    TestClient(app).post("/tickets/closed", json=sample_request(ticket_id))

    raw    = (tmp_path / "raw-route" / f"{ticket_id}.json").read_text(encoding="utf-8")
    thread = (tmp_path / "anonymized" / f"{ticket_id}.txt").read_text(encoding="utf-8")
    card   = ParsedTicket.model_validate_json(
        (tmp_path / "cards" / f"{ticket_id}.json").read_text(encoding="utf-8")
    )

    assert RawTicket.model_validate_json(raw) == sample_raw_ticket(ticket_id)
    assert thread == sample_thread(ticket_id).text
    assert PERSON not in thread
    assert (card.ticket_id, card.date) == (ticket_id, sample_raw_ticket().date)


def test_a_blocked_ticket_leaves_the_corpus_untouched(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie zablokowane przez bramkę nie zostawia w korpusie żadnego pliku
    i nie dotyka indeksów, graf karty nie rusza (jego anonimizator nic nie dostał, jedno
    wywołanie modelu, log samej bramki), a odpowiedź niesie werdykt „block” z uzasadnieniem,
    wskazówką i furtką.

    Wyłapuje trasę, która po blokadzie i tak robi kartę albo zapisuje zgłoszenie: do bazy wiedzy
    trafiałyby zamknięcia bez opisu problemu i rozwiązania, a każde kosztowałoby drugi przebieg
    modelu. Wyłapuje też blokadę bez powodów: helpdesk nie miałby czego pokazać (zasada 10)."""
    tickets, threads = FakeTickets(), FakeThreads()
    anonymizer       = ReplacingAnonymizer(PERSON, PERSON_MARKERS)
    corpus           = closed_ticket_indexer_on(tmp_path, tickets, threads)
    app              = app_closing_tickets(corpus, sample_block(), sample_card(), anonymizer)

    response = TestClient(app).post("/tickets/closed", json=sample_request())
    body     = response.json()

    assert response.status_code == 200
    assert list(tmp_path.iterdir()) == []
    assert (tickets.calls, threads.calls) == ([], [])
    assert anonymizer.texts == []
    assert (body["outcome"], body["replaced"], body["verdict"]) == ("blocked", False, "block")
    assert (body["reasons"], body["hint"]) == (sample_block().reasons, sample_block().hint)
    assert body["overridable"] is True
    assert (body["useful_reason"], body["dropped_by"]) == (None, [])
    assert body["usage"]["llm_calls"] == 1
    assert [entry["node"] for entry in body["log"]] == GRAPH_NODES


def test_a_card_dropped_by_the_filter_is_reported_with_its_rule(tmp_path: Path) -> None:
    """Sprawdza, czy karta, którą model ocenił jako nieprzydatną, kończy się odpowiedzią
    „odrzucona przez filtr” z regułą `not_useful` i uzasadnieniem modelu jako fragmentem, który
    ją uruchomił, a karta zostaje w korpusie.

    Wyłapuje trasę, która mówi „zaindeksowane” o karcie, której nie ma w indeksach, albo nie
    mówi, dlaczego karta odpadła: wdrożeniowiec nie wiedziałby, że zamknięcie nic nie dało bazie
    wiedzy i co dopisać przy ponownym zamknięciu."""
    reason     = "Wątek tylko potwierdza zamknięcie."
    card       = sample_card(useful=False, useful_reason=reason)
    anonymizer = ReplacingAnonymizer(PERSON, PERSON_MARKERS)
    corpus     = closed_ticket_indexer_on(tmp_path, FakeTickets(), FakeThreads())
    app        = app_closing_tickets(corpus, sample_pass(), card, anonymizer)

    body = TestClient(app).post("/tickets/closed", json=sample_request()).json()

    assert (tmp_path / "cards" / f"{TICKET_ID}.json").exists()
    assert body["outcome"]       == "dropped"
    assert body["useful_reason"] == reason
    assert body["dropped_by"]    == [{"rule": "not_useful", "evidence": reason}]


def test_closing_the_same_ticket_again_says_the_card_was_replaced(tmp_path: Path) -> None:
    """Sprawdza, czy drugie zamknięcie tego samego zgłoszenia odpowiada `replaced` = true,
    a pierwsze `replaced` = false.

    Wyłapuje trasę, która gubi tę informację z raportu serwisu: helpdesk nie wiedziałby, że
    ponowne zamknięcie zmieniło istniejący wpis w bazie wiedzy."""
    anonymizer = ReplacingAnonymizer(PERSON, PERSON_MARKERS)
    corpus     = closed_ticket_indexer_on(tmp_path, FakeTickets(), FakeThreads())
    client     = TestClient(app_closing_tickets(corpus, sample_pass(), sample_card(), anonymizer))

    first  = client.post("/tickets/closed", json=sample_request()).json()
    second = client.post("/tickets/closed", json=sample_request()).json()

    assert (first["replaced"], second["replaced"]) == (False, True)


def test_an_index_failure_is_503_and_the_files_stay(tmp_path: Path) -> None:
    """Sprawdza, czy awaria Qdranta przy dokładaniu karty kończy się statusem 503 we wspólnym
    kształcie błędu, a trzy pliki zgłoszenia zostają w korpusie.

    Wyłapuje awarię indeksu oddaną jako 500 albo jako udane zamknięcie: helpdesk nie wiedziałby,
    że może ponowić, albo uznałby, że zgłoszenie jest w bazie wiedzy, choć do czasu przebudowy
    indeksu go tam nie ma."""
    tickets    = FakeTickets(upsert_error=DbQdrantError("Qdrant odrzucił zapis"))
    anonymizer = ReplacingAnonymizer(PERSON, PERSON_MARKERS)
    corpus     = closed_ticket_indexer_on(tmp_path, tickets, FakeThreads())
    app        = app_closing_tickets(corpus, sample_pass(), sample_card(), anonymizer)

    response = TestClient(app).post("/tickets/closed", json=sample_request())

    assert response.status_code == 503
    assert set(response.json()) == {"detail", "request_id"}
    assert (tmp_path / "raw-route" / f"{TICKET_ID}.json").exists()
    assert (tmp_path / "anonymized" / f"{TICKET_ID}.txt").exists()
    assert (tmp_path / "cards" / f"{TICKET_ID}.json").exists()


def test_the_fake_model_cannot_close_tickets_into_the_corpus() -> None:
    """Sprawdza, czy przy atrapie modelu generującego (domyślna konfiguracja testów) trasa kończy
    się błędem konfiguracji `ClosedTicketConfigError`, zanim cokolwiek uruchomi.

    Wyłapuje trasę, która przy atrapie modelu pisze do korpusu: atrapa grafu karty oddaje zawsze
    tę samą zmyśloną kartę, a anonimizator przyjmuje wtedy tekst bez zmian, więc w `anonymized/`
    i w tabeli wątków stanęłyby dane osobowe."""
    with pytest.raises(ClosedTicketConfigError):
        TestClient(create_app()).post("/tickets/closed", json=sample_request())
