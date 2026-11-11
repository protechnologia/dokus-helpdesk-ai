from pathlib import Path

import pytest

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.raw_ticket import RawTicket
from app.db_qdrant import DbQdrantError
from tests._helpers.tickets_index import FakeThreads, FakeTickets, closed_ticket_indexer_on
from tests._helpers.tickets_index.samples import (
    PERSON,
    TICKET_ID,
    sample_card,
    sample_raw_ticket,
    sample_thread,
)

# Serwis zamkniętego zgłoszenia na katalogu tymczasowym: pliki korpusu naprawdę trafiają na dysk,
# indekser kart jest prawdziwy, a embedder, kolekcja i tabela wątków to atrapy zapisujące, co
# dostały. Że Qdrant i Postgres przyjmują zapis i usuwanie, sprawdzają testy kolekcji i tabeli na
# stacku.


async def test_the_three_files_land_in_the_corpus(tmp_path: Path) -> None:
    """Sprawdza, czy zamknięte zgłoszenie zostawia w korpusie trzy pliki pod swoim numerem:
    surowe zgłoszenie w `raw-route/`, wątek po anonimizacji w `anonymized/` i kartę w `cards/`,
    każdy z treścią, z której da się odtworzyć to, co serwis dostał.

    Wyłapuje plik zapisany w złym katalogu, pod złą nazwą albo w kształcie, którego nie da się
    wczytać: indeks nie odbudowałby się z plików, a zgłoszenia z trasy nie dałoby się zanonimizować
    od nowa."""
    raw, thread, card = sample_raw_ticket(), sample_thread(), sample_card()

    await closed_ticket_indexer_on(tmp_path, FakeTickets(), FakeThreads()).add(raw, thread, card)

    raw_file    = tmp_path / "raw-route" / f"{TICKET_ID}.json"
    thread_file = tmp_path / "anonymized" / f"{TICKET_ID}.txt"
    card_file   = tmp_path / "cards" / f"{TICKET_ID}.json"

    assert RawTicket.model_validate_json(raw_file.read_text(encoding="utf-8"))      == raw
    assert thread_file.read_text(encoding="utf-8")                                  == thread.text
    assert ParsedTicket.model_validate_json(card_file.read_text(encoding="utf-8")) == card


async def test_a_kept_card_goes_to_both_indexes(tmp_path: Path) -> None:
    """Sprawdza, czy karta przyjęta przez filtr trafia jako punkt do kolekcji zgłoszeń, a jej
    wątek po anonimizacji jako wiersz do tabeli wątków (po założeniu tabeli), bez osoby ze
    zgłoszenia, i czy raport mówi: zaindeksowana, nie zastąpiła innej, bez odrzuceń.

    Wyłapuje kartę, która zostaje tylko na dysku albo trafia do jednego indeksu: zamknięte
    zgłoszenie nie dałoby się znaleźć po znaczeniu albo jego wątek nie dałby się przeczytać.
    Wyłapuje też surowy wątek w tabeli: dane osobowe trafiłyby do wyszukiwania i do modelu."""
    tickets, threads = FakeTickets(), FakeThreads()

    report = await closed_ticket_indexer_on(tmp_path, tickets, threads).add(
        sample_raw_ticket(), sample_thread(), sample_card()
    )

    assert [point.ticket_id for point in tickets.points] == [TICKET_ID]
    assert threads.calls == ["create", "upsert:1"]
    assert threads.rows[0].ticket_id == TICKET_ID
    assert threads.rows[0].thread    == sample_thread().text
    assert PERSON not in threads.rows[0].thread
    assert (report.indexed, report.replaced, report.dropped_by) == (True, False, [])


async def test_a_dropped_card_stays_on_disk_and_leaves_both_indexes(tmp_path: Path) -> None:
    """Sprawdza, czy karta odrzucona przez filtr (`useful` = false) zostaje zapisana na dysku, ale
    z obu indeksów jest usuwana po numerze, nic do nich nie trafia, a raport mówi: niezaindeksowana,
    odrzucona regułą `not_useful`.

    Wyłapuje kartę bez wiedzy, która trafia do wyszukiwania, oraz zgłoszenie zamknięte ponownie,
    którego stara karta zostaje w indeksie po tym, jak nowa odpadła; wyłapuje też kartę, która
    znika z dysku, choć zmieniony filtr mógłby ją kiedyś przyjąć."""
    tickets, threads = FakeTickets(), FakeThreads()
    card             = sample_card(useful=False, useful_reason="Wątek tylko potwierdza zamknięcie.")

    report = await closed_ticket_indexer_on(tmp_path, tickets, threads).add(
        sample_raw_ticket(), sample_thread(), card
    )

    assert (tmp_path / "cards" / f"{TICKET_ID}.json").exists()
    assert tickets.points == []
    assert tickets.calls  == ["ensure", f"delete:{TICKET_ID}"]
    assert threads.calls  == ["create", f"delete:{TICKET_ID}"]
    assert report.indexed is False
    assert [hit.rule for hit in report.dropped_by] == ["not_useful"]


async def test_closing_again_replaces_the_card_and_says_so(tmp_path: Path) -> None:
    """Sprawdza, czy drugie zamknięcie tego samego zgłoszenia nadpisuje jego kartę nową i czy
    raport drugiego zamknięcia mówi, że karta zastąpiła wcześniejszą, a raport pierwszego — że nie.

    Wyłapuje ponowne zamknięcie, które zostawia starą kartę albo nie mówi, że ją zastąpiło:
    korpus trzymałby ustalenia sprzed ponownego otwarcia, a wołający nie wiedziałby, że zmienił
    istniejący wpis."""
    service = closed_ticket_indexer_on(tmp_path, FakeTickets(), FakeThreads())
    newer   = sample_card(solution="Wznowiono kolejkę odbioru i włączono jej monitorowanie.")

    first  = await service.add(sample_raw_ticket(), sample_thread(), sample_card())
    second = await service.add(sample_raw_ticket(), sample_thread(), newer)

    stored = (tmp_path / "cards" / f"{TICKET_ID}.json").read_text(encoding="utf-8")

    assert (first.replaced, second.replaced) == (False, True)
    assert ParsedTicket.model_validate_json(stored) == newer


async def test_cards_of_another_ticket_are_refused_before_anything_is_written(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy zgłoszenie 41003 z kartą zgłoszenia 41002 kończy się błędem `ValueError`,
    zanim cokolwiek trafi na dysk albo do indeksów.

    Wyłapuje pomyłkę wołającego, po której karta jednego zgłoszenia leżałaby obok wątku innego:
    agent czytałby wtedy pod jednym numerem przyczynę z cudzej sprawy."""
    tickets, threads = FakeTickets(), FakeThreads()

    with pytest.raises(ValueError):
        await closed_ticket_indexer_on(tmp_path, tickets, threads).add(
            sample_raw_ticket("41003"), sample_thread("41003"), sample_card()
        )

    assert list(tmp_path.iterdir()) == []
    assert (tickets.calls, threads.calls) == ([], [])


async def test_the_files_stay_when_an_index_fails(tmp_path: Path) -> None:
    """Sprawdza, czy przy awarii Qdranta w trakcie dokładania karty błąd `DbQdrantError` dochodzi
    do wołającego, a trzy pliki zgłoszenia zostają w korpusie.

    Wyłapuje kolejność, w której indeks idzie przed plikami: awaria bazy zabrałaby wtedy
    zgłoszenie w ogóle, choć pliki są źródłem prawdy, z którego `helpdesk tickets reindex`
    odbudowuje indeks."""
    tickets = FakeTickets(upsert_error=DbQdrantError("Qdrant odrzucił zapis"))

    with pytest.raises(DbQdrantError):
        await closed_ticket_indexer_on(tmp_path, tickets, FakeThreads()).add(
            sample_raw_ticket(), sample_thread(), sample_card()
        )

    assert (tmp_path / "raw-route" / f"{TICKET_ID}.json").exists()
    assert (tmp_path / "anonymized" / f"{TICKET_ID}.txt").exists()
    assert (tmp_path / "cards" / f"{TICKET_ID}.json").exists()


async def test_aclose_closes_both_indexes(tmp_path: Path) -> None:
    """Sprawdza, czy `aclose()` serwisu zamyka kolekcję zgłoszeń i tabelę wątków.

    Wyłapuje serwis, który zostawia otwarte połączenia: trasa budująca go na każde zamknięcie
    zgłoszenia wyczerpałaby z czasem pulę połączeń Postgresa."""
    tickets, threads = FakeTickets(), FakeThreads()

    await closed_ticket_indexer_on(tmp_path, tickets, threads).aclose()

    assert tickets.calls[-1] == "aclose"
    assert threads.calls     == ["aclose"]
