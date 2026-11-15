from pathlib import Path

import pytest

from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.indexer_tickets import EMBED_BATCH_SIZE, TicketsIndexer
from app.db_postgres import PostgresClient, TicketsTable
from app.db_qdrant import (
    VECTOR_PROBLEM,
    VECTOR_STS,
    QdrantClient,
    TicketsCollection,
)
from app.engine_embedding import EmbeddingConfigError
from tests._helpers.embedding import EMBEDDING_MODEL, OTHER_MODEL
from tests._helpers.tickets_index import (
    VECTOR_SIZE,
    FakeEmbedder,
    FakeThreads,
    FakeTickets,
    tickets_indexer_on,
    write_card,
    write_thread,
)
from tests._helpers.tickets_index.samples import TICKET_ID, sample_card, sample_thread

# Indekser zgłoszeń na korpusie w katalogu testu: karty i wątki naprawdę leżą na dysku, a embedder,
# kolekcja zgłoszeń i tabela wątków to atrapy zapisujące, co dostały. Że Qdrant i Postgres
# przyjmują zapis, sprawdzają testy kolekcji i tabeli na stacku.


async def test_good_tickets_are_indexed(tmp_path: Path) -> None:
    """Sprawdza, czy z korpusu z dwoma poprawnymi zgłoszeniami oba trafiają do indeksu (raport
    mówi: wczytano 2, zaindeksowano 2) i czy pierwszą rzeczą, jaką indekser robi z kolekcją, jest
    upewnienie się, że ona istnieje.

    Wyłapuje indekser, który gubi poprawne zgłoszenia albo zaczyna zapisywać punkty do kolekcji,
    której jeszcze nie ma — taki przebieg kończyłby się błędem bazy zamiast zbudowanym
    indeksem."""
    write_card(tmp_path, sample_card(ticket_id="1"))
    write_card(tmp_path, sample_card(ticket_id="2"))

    tickets = FakeTickets()
    report  = await tickets_indexer_on(tickets).build(TicketsCorpus(root=tmp_path))

    assert report.read    == 2
    assert report.indexed == 2
    assert tickets.calls[0] == "ensure"


async def test_hollow_tickets_are_dropped_with_a_reason(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie bez wiedzy (model ocenił kartę jako nieprzydatną) nie trafia do
    indeksu, a raport podaje powód: z dwóch wczytanych zgłoszeń jedno jest zaindeksowane, a jedno
    odrzucone regułą `not_useful`.

    Wyłapuje dwie usterki: puste zgłoszenie w indeksie, które przy wyszukiwaniu wygląda na
    odpowiedź, oraz odrzucenie bez podanego powodu, którego nie da się odróżnić od błędu
    w czytaniu plików."""
    write_card(tmp_path, sample_card(ticket_id="1"))
    write_card(tmp_path, sample_card(ticket_id="2", useful=False, useful_reason="Nic."))

    report = await tickets_indexer_on(FakeTickets()).build(TicketsCorpus(root=tmp_path))

    assert report.read    == 2
    assert report.indexed == 1
    assert report.dropped == 1
    assert report.filtered.by_reason() == {"not_useful": 1}


async def test_both_named_vectors_are_built(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie dostaje w indeksie oba wektory i czy każdy pochodzi z właściwego
    trybu embeddera: wektor `problem` z trybu passage, wektor `sts` z trybu sts, a punkt niesie
    nazwę modelu z odpowiedzi embeddera. Atrapa embeddera oddaje w każdym trybie inne liczby,
    więc zamianę widać.

    Wyłapuje wektory zamienione miejscami albo brak jednego z nich. Zamiany nie widać po fakcie,
    bo oba wektory dalej wyglądają poprawnie, a brakujący wektor oznaczałby później ponowną
    indeksację całego korpusu. Wyłapuje też punkt z modelem innym niż ten, który policzył
    wektory: kolekcja nie umiałaby wtedy odmówić mieszania modeli."""
    write_card(tmp_path, sample_card(ticket_id="1"))

    embedder = FakeEmbedder()
    tickets  = FakeTickets()

    await tickets_indexer_on(tickets, embedder=embedder).build(TicketsCorpus(root=tmp_path))

    point = tickets.points[0]

    assert point.vector_problem  == [1.0] * VECTOR_SIZE  # z embed_passage
    assert point.vector_sts      == [2.0] * VECTOR_SIZE  # z embed_sts
    assert point.embedding_model == EMBEDDING_MODEL
    assert point.to_qdrant()["vector"].keys() == {VECTOR_PROBLEM, VECTOR_STS}


async def test_both_modes_receive_the_same_text(tmp_path: Path) -> None:
    """Sprawdza, czy oba tryby embeddera, passage i sts, dostają dokładnie te same teksty.

    Wyłapuje rozjazd tekstów między trybami: oba wektory opisują jedno zgłoszenie, więc gdyby
    powstały z różnych tekstów, zgłoszenie byłoby wyszukiwane jako jedno, a porównywane z innymi
    jako coś innego."""
    write_card(tmp_path, sample_card(ticket_id="1"))

    embedder = FakeEmbedder()
    indexer  = tickets_indexer_on(FakeTickets(), embedder=embedder)

    await indexer.build(TicketsCorpus(root=tmp_path))

    assert embedder.passage_batches == embedder.sts_batches


async def test_two_models_in_one_batch_stop_the_build(tmp_path: Path) -> None:
    """Sprawdza, czy indeksacja kończy się błędem konfiguracji `EmbeddingConfigError`, który
    nazywa oba modele, i niczego nie zapisuje, gdy embedder policzył wektory `problem` i `sts`
    tej samej paczki dwoma różnymi modelami.

    Wyłapuje indekser, który bierze model z jednego wywołania i nie patrzy na drugie: punkt
    zapisałby jeden model przy wektorze `sts` policzonym innym, a tego nie wykryje już nic."""
    write_card(tmp_path, sample_card(ticket_id="1"))

    tickets = FakeTickets()
    indexer = tickets_indexer_on(tickets, embedder=FakeEmbedder(sts_model=OTHER_MODEL))

    with pytest.raises(EmbeddingConfigError, match=OTHER_MODEL):
        await indexer.build(TicketsCorpus(root=tmp_path))

    assert tickets.points == []


async def test_embedding_text_comes_from_the_model(tmp_path: Path) -> None:
    """Sprawdza, czy tekst wysyłany do embeddera zawiera opis problemu i objawy zgłoszenia,
    a nie zawiera rozwiązania.

    Wyłapuje rozwiązanie, które trafiło do wektora: szukamy zgłoszeń o podobnym problemie,
    a wektor z domieszką odpowiedzi mieszałby podobieństwo problemu z podobieństwem
    rozwiązania."""
    write_card(tmp_path, sample_card(ticket_id="1"))

    embedder = FakeEmbedder()
    indexer  = tickets_indexer_on(FakeTickets(), embedder=embedder)

    await indexer.build(TicketsCorpus(root=tmp_path))

    sent = embedder.passage_batches[0][0]

    assert sample_card().problem  in sent
    assert sample_card().symptoms in sent
    assert sample_card().solution not in sent


async def test_large_corpus_is_embedded_in_batches(tmp_path: Path) -> None:
    """Sprawdza, czy przy liczbie zgłoszeń o pięć większej, niż mieści jedna paczka, indekser
    woła embedder więcej niż raz, paczki razem niosą tyle tekstów, ile jest zgłoszeń, i wszystkie
    zgłoszenia są zaindeksowane.

    Wyłapuje dwie usterki: cały korpus wysłany jednym żądaniem, przez co jedno przekroczenie
    czasu kładzie cały przebieg, oraz zgłoszenia zgubione albo powtórzone na granicy paczek."""
    count = EMBED_BATCH_SIZE + 5

    for number in range(count):
        write_card(tmp_path, sample_card(ticket_id=f"{number:04d}"))

    embedder = FakeEmbedder()
    indexer  = tickets_indexer_on(FakeTickets(), embedder=embedder)
    report   = await indexer.build(TicketsCorpus(root=tmp_path))

    assert report.indexed == count
    assert len(embedder.passage_batches) > 1
    assert sum(len(batch) for batch in embedder.passage_batches) == count


async def test_threads_of_kept_cards_go_to_the_table(tmp_path: Path) -> None:
    """Sprawdza, czy z korpusu z wątkami do tabeli wątków trafia (po jej założeniu) wątek karty
    przyjętej, z datą karty i treścią pliku z `anonymized/`, a wątek karty odrzuconej nie trafia,
    i czy raport mówi o jednym wątku.

    Wyłapuje budowę, która pomija tabelę wątków — wyszukiwanie po słowach i odczyt wątku nie
    widziałyby korpusu — albo wpuszcza do niej wątki kart odrzuconych: agent znajdowałby po
    słowach zgłoszenia, których karty nie ma w indeksie (decyzja 2026-11-11)."""
    write_card(tmp_path, sample_card(ticket_id="1"))
    write_card(tmp_path, sample_card(ticket_id="2", useful=False, useful_reason="Nic."))
    write_thread(tmp_path, "1", sample_thread("1"))
    write_thread(tmp_path, "2", sample_thread("2"))

    threads = FakeThreads()
    report  = await tickets_indexer_on(FakeTickets(), threads).build(TicketsCorpus(root=tmp_path))

    assert threads.calls == ["create", "upsert:1"]
    assert [(row.ticket_id, row.ticket_date) for row in threads.rows] == [("1", sample_card().date)]
    assert threads.rows[0].thread == sample_thread("1").text
    assert report.threads == 1


async def test_a_corpus_without_threads_leaves_the_table_alone(tmp_path: Path) -> None:
    """Sprawdza, czy korpus bez katalogu `anonymized/` (same karty) buduje karty, nie dotyka
    tabeli wątków i daje raport z `threads` równym `None`.

    Wyłapuje budowę, która przy braku wątków zakłada albo czyści tabelę: indeksacja golden setu
    zabrałaby wtedy wątki korpusu z wyszukiwania po słowach."""
    write_card(tmp_path, sample_card(ticket_id="1"))

    threads = FakeThreads()
    report  = await tickets_indexer_on(FakeTickets(), threads).build(TicketsCorpus(root=tmp_path))

    assert report.indexed == 1
    assert threads.calls  == []
    assert report.threads is None


async def test_a_card_without_its_thread_stops_the_build_before_anything(tmp_path: Path) -> None:
    """Sprawdza, czy korpus z `anonymized/`, w którym karta 2 nie ma wątku, kończy się błędem
    `FileNotFoundError` z jej numerem, zanim cokolwiek trafi do kolekcji albo tabeli.

    Wyłapuje budowę, która pomija kartę bez wątku po cichu albo zapisuje karty i pada dopiero
    przy wątkach: zepsuty korpus dałby indeksy, w których karta i wątek się rozjeżdżają."""
    write_card(tmp_path, sample_card(ticket_id="1"))
    write_card(tmp_path, sample_card(ticket_id="2"))
    write_thread(tmp_path, "1", sample_thread("1"))

    tickets, threads = FakeTickets(), FakeThreads()

    with pytest.raises(FileNotFoundError, match="2"):
        await tickets_indexer_on(tickets, threads).build(TicketsCorpus(root=tmp_path))

    assert (tickets.calls, threads.calls) == ([], [])


async def test_add_writes_one_card_and_its_thread() -> None:
    """Sprawdza, czy `add()` zakłada kolekcję i tabelę wątków, gdy ich nie ma, zapisuje jeden
    punkt karty i jeden wiersz z jej wątkiem, bez czytania żadnego katalogu.

    Wyłapuje dokładanie, które pomija zakładanie kolekcji albo tabeli albo gubi kartę lub wątek:
    pierwsze zamknięte zgłoszenie na świeżej instancji kończyłoby się błędem brakującego
    indeksu, a zgłoszenie nie trafiałoby do wyszukiwania."""
    tickets, threads = FakeTickets(), FakeThreads()

    await tickets_indexer_on(tickets, threads).add(sample_card(), sample_thread())

    assert tickets.calls == ["ensure", "upsert:1"]
    assert threads.calls == ["create", "upsert:1"]
    assert [point.ticket_id for point in tickets.points] == [TICKET_ID]
    assert threads.rows[0].thread == sample_thread().text


async def test_remove_deletes_the_given_numbers_from_both_indexes() -> None:
    """Sprawdza, czy `remove()` zakłada kolekcję i tabelę, gdy ich nie ma, i usuwa z obu punkty
    i wiersze o podanych numerach, niczego nie zapisując.

    Wyłapuje usuwanie, które pomija jeden z indeksów albo zapisuje zamiast usuwać: karta
    odrzucona przy ponownym zamknięciu zgłoszenia zostałaby w wynikach wyszukiwania."""
    tickets, threads = FakeTickets(), FakeThreads()

    await tickets_indexer_on(tickets, threads).remove([TICKET_ID])

    assert tickets.calls == ["ensure", f"delete:{TICKET_ID}"]
    assert threads.calls == ["create", f"delete:{TICKET_ID}"]


async def test_rebuild_drops_both_indexes_first(tmp_path: Path) -> None:
    """Sprawdza, czy pełna odbudowa korpusu z wątkami najpierw kasuje kolekcję i tabelę wątków,
    a dopiero potem zakłada je od nowa.

    Wyłapuje odbudowę, która nie kasuje starego indeksu: punkty i wiersze zgłoszeń, których
    w korpusie już nie ma, zostałyby pod spodem i dalej wracały w wynikach wyszukiwania."""
    write_card(tmp_path, sample_card(ticket_id="1"))
    write_thread(tmp_path, "1", sample_thread("1"))

    tickets, threads = FakeTickets(), FakeThreads()

    await tickets_indexer_on(tickets, threads).rebuild(TicketsCorpus(root=tmp_path))

    assert tickets.calls[:2] == ["drop", "ensure"]
    assert threads.calls     == ["drop", "create", "upsert:1"]


async def test_rebuild_without_threads_keeps_the_table(tmp_path: Path) -> None:
    """Sprawdza, czy przebudowa korpusu bez `anonymized/` kasuje i buduje kolekcję, a tabeli
    wątków nie rusza.

    Wyłapuje przebudowę golden setu, która kasuje tabelę wątków korpusu, choć nie ma czym jej
    napełnić."""
    write_card(tmp_path, sample_card(ticket_id="1"))

    tickets, threads = FakeTickets(), FakeThreads()

    await tickets_indexer_on(tickets, threads).rebuild(TicketsCorpus(root=tmp_path))

    assert tickets.calls[0] == "drop"
    assert threads.calls    == []


async def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    """Sprawdza, czy dwie odbudowy z tego samego korpusu dają punkty o tych samych
    identyfikatorach — identyfikator punktu wynika z numeru zgłoszenia.

    Wyłapuje identyfikatory nadawane losowo albo zależne od przebiegu: ponowna indeksacja
    dokładałaby wtedy drugi komplet punktów, zamiast nadpisać pierwszy."""
    write_card(tmp_path, sample_card(ticket_id="1"))
    write_card(tmp_path, sample_card(ticket_id="2"))

    first  = FakeTickets()
    second = FakeTickets()

    await tickets_indexer_on(first).rebuild(TicketsCorpus(root=tmp_path))
    await tickets_indexer_on(second).rebuild(TicketsCorpus(root=tmp_path))

    assert [p.point_id for p in first.points] == [p.point_id for p in second.points]


async def test_rebuild_of_a_missing_directory_keeps_the_indexes(tmp_path: Path) -> None:
    """Sprawdza, czy przebudowa korpusu, którego nie ma, kończy się `NotADirectoryError`
    i nie kasuje kolekcji ani tabeli.

    Wyłapuje przebudowę, która najpierw kasuje, a dopiero potem szuka katalogu: literówka
    w ścieżce albo domyślny katalog, którego jeszcze nie ma, zostawiłyby pusty indeks."""
    tickets, threads = FakeTickets(), FakeThreads()

    with pytest.raises(NotADirectoryError):
        await tickets_indexer_on(tickets, threads).rebuild(TicketsCorpus(root=tmp_path / "nie-ma"))

    assert "drop" not in tickets.calls + threads.calls


async def test_rebuild_of_a_corpus_without_cards_keeps_the_indexes(tmp_path: Path) -> None:
    """Sprawdza, czy przebudowa korpusu z pustym `cards/` kończy się `FileNotFoundError` i nie
    kasuje kolekcji ani tabeli.

    Wyłapuje przebudowę, która kasuje indeksy, choć nie ma ich z czego odbudować: wyszukiwanie
    zgłoszeń straciłoby cały indeks przez wskazanie pustego korpusu."""
    corpus = TicketsCorpus(root=tmp_path)
    corpus.cards_dir.mkdir()
    corpus.anonymized_dir.mkdir()

    tickets, threads = FakeTickets(), FakeThreads()

    with pytest.raises(FileNotFoundError):
        await tickets_indexer_on(tickets, threads).rebuild(corpus)

    assert "drop" not in tickets.calls + threads.calls


async def test_rebuild_with_a_card_without_its_thread_keeps_the_indexes(tmp_path: Path) -> None:
    """Sprawdza, czy przebudowa korpusu z `anonymized/`, w którym karta nie ma wątku, kończy się
    `FileNotFoundError` i nie kasuje kolekcji ani tabeli.

    Wyłapuje przebudowę, która sprawdza wątki dopiero po skasowaniu: zepsuty korpus zostawiłby
    puste indeksy, a do czasu naprawy korpusu agent nie miałby w czym szukać."""
    write_card(tmp_path, sample_card(ticket_id="1"))
    TicketsCorpus(root=tmp_path).anonymized_dir.mkdir()

    tickets, threads = FakeTickets(), FakeThreads()

    with pytest.raises(FileNotFoundError):
        await tickets_indexer_on(tickets, threads).rebuild(TicketsCorpus(root=tmp_path))

    assert "drop" not in tickets.calls + threads.calls


async def test_missing_directory_is_an_error(tmp_path: Path) -> None:
    """Sprawdza, czy wskazanie korpusu, którego nie ma, kończy się błędem `NotADirectoryError`.

    Wyłapuje indekser, który przy literówce w ścieżce kończy pracę bez błędu, z zerem zgłoszeń —
    pusty przebieg wyglądałby wtedy na udany."""
    with pytest.raises(NotADirectoryError):
        await tickets_indexer_on(FakeTickets()).build(TicketsCorpus(root=tmp_path / "nie-ma"))


async def test_empty_directory_indexes_nothing(tmp_path: Path) -> None:
    """Sprawdza, czy korpus z pustym `cards/` daje pusty raport (wczytano 0, zaindeksowano 0),
    a nie wyjątek.

    Wyłapuje indekser, który wywraca się, gdy nie ma czego indeksować. Co zrobić z pustym
    wynikiem, decyduje komenda, która indekser wywołała, więc musi dostać raport."""
    corpus = TicketsCorpus(root=tmp_path)
    corpus.cards_dir.mkdir()

    report = await tickets_indexer_on(FakeTickets()).build(corpus)

    assert report.read    == 0
    assert report.indexed == 0


async def test_silent_filter_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy raport niesie ostrzeżenie, gdy z 60 zgłoszeń filtr jakości nie odrzucił
    żadnego — to dość dużo zgłoszeń, żeby brak odrzuceń był podejrzany.

    Wyłapuje zniknięcie tego ostrzeżenia. Reguły filtra czytają tekst pisany przez model, więc
    po zmianie promptu albo modelu mogą przestać pasować do czegokolwiek i same tego nie
    zauważą: puste zgłoszenia wchodziłyby do indeksu, a jedynym sygnałem jest liczba
    odrzuconych."""
    for number in range(60):
        write_card(tmp_path, sample_card(ticket_id=f"{number:04d}"))

    report = await tickets_indexer_on(FakeTickets()).build(TicketsCorpus(root=tmp_path))

    assert report.warnings


async def test_aclose_closes_the_embedder_the_collection_and_the_table() -> None:
    """Sprawdza, czy zamknięcie indeksera zamyka embedder, kolekcję i tabelę wątków.

    Wyłapuje połączenie zostawione otwarte: kto trzyma sam indekser, na przykład komenda,
    sprząta jednym wywołaniem i nie ma jak zamknąć reszty osobno."""
    embedder = FakeEmbedder()
    tickets  = FakeTickets()
    threads  = FakeThreads()

    await tickets_indexer_on(tickets, threads, embedder=embedder).aclose()

    assert embedder.closed
    assert tickets.calls == ["aclose"]
    assert threads.calls == ["aclose"]


def test_indexer_takes_clients_it_does_not_build() -> None:
    """Sprawdza, czy indekser da się zbudować z podanego embeddera, podanej kolekcji i podanej
    tabeli — tu z prawdziwymi klasami kolekcji i tabeli i adresami, z którymi test się nie łączy.

    Wyłapuje konstruktor, który przestał przyjmować gotowych klientów albo przy budowie sam
    sięga po sieć: indekser zależałby wtedy od działającej usługi, a testy z tego pliku nie
    mogłyby podstawić atrap."""
    tickets = TicketsCollection(
        client      = QdrantClient(base_url="http://qdrant:6333"),
        name        = "tickets",
        vector_size = VECTOR_SIZE,
    )
    postgres = PostgresClient(
        host     = "postgres",
        port     = 5432,
        database = "helpdesk",
        user     = "helpdesk",
        password = "haslo",
    )
    threads = TicketsTable(postgres)
    indexer = TicketsIndexer(embedder=FakeEmbedder(), tickets=tickets, threads=threads)

    assert indexer is not None
