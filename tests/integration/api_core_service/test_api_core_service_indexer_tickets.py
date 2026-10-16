import json
from pathlib import Path

import pytest

from app.core_service.indexer_tickets import EMBED_BATCH_SIZE, TicketsIndexer
from app.db_qdrant import (
    VECTOR_PROBLEM,
    VECTOR_STS,
    QdrantClient,
    TicketPoint,
    TicketsCollection,
)
from app.engine_embedding import EmbeddingConfigError, Embeddings
from tests._helpers.embedding import EMBEDDING_MODEL, OTHER_MODEL

VECTOR_SIZE = 4

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


class FakeEmbedder:
    """
    Description:
    Zastępuje `EmbeddingClient`: oddaje wektor na tekst z nazwą modelu i zapisuje, w którym
    TRYBIE poszła każda paczka.

    Stub, a nie atrapa z produkcji: `FakeEncoder` stoi po drugiej stronie HTTP, w usłudze
    `embedder`, więc klient nie ma własnej wersji offline. Liczy się tu, że indeksacja woła
    passage i sts osobno — zamiany jednego z drugim nie widać po fakcie, bo oba wektory dalej
    wyglądają poprawnie.
    """

    def __init__(
        self,
        sts_model: str = EMBEDDING_MODEL,  # np. "inny-model" — gdy test zmienia model w trybie sts
    ) -> None:
        """
        Description:
        Buduje stub z pustymi zapisami wywołań. Tryb passage oddaje zawsze `EMBEDDING_MODEL`,
        a tryb sts model podany tutaj.

        Example args:
            sts_model="model-testowy"

        Example result:
            FakeEmbedder z pustymi `passage_batches` i `sts_batches`
        """
        self.passage_batches: list[list[str]] = []
        self.sts_batches:     list[list[str]] = []
        self.closed     = False
        self._sts_model = sts_model

    async def embed_passage(
        self,
        texts: list[str],  # np. ["Wysyłka przez ePUAP…"]
    ) -> Embeddings:
        """
        Description:
        Zapisuje paczkę i oddaje rozpoznawalny wektor na każdy tekst.

        Example args:
            texts=["Wysyłka przez ePUAP…"]

        Example result:
            Embeddings(model="model-testowy", vectors=[[1.0, 1.0, 1.0, 1.0]])
        """
        self.passage_batches.append(texts)

        return Embeddings(model=EMBEDDING_MODEL, vectors=[[1.0] * VECTOR_SIZE for _ in texts])

    async def embed_sts(
        self,
        texts: list[str],  # np. ["Wysyłka przez ePUAP…"]
    ) -> Embeddings:
        """
        Description:
        Zapisuje paczkę i oddaje wektor inny niż w trybie passage, żeby zamienioną parę było
        widać w asercjach.

        Example args:
            texts=["Wysyłka przez ePUAP…"]

        Example result:
            Embeddings(model="model-testowy", vectors=[[2.0, 2.0, 2.0, 2.0]])
        """
        self.sts_batches.append(texts)

        return Embeddings(model=self._sts_model, vectors=[[2.0] * VECTOR_SIZE for _ in texts])

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje, że stub został zamknięty.

        Example args:
            (brak)

        Example result:
            None
        """
        self.closed = True


class FakeTickets:
    """
    Description:
    Zastępuje `TicketsCollection`: zapisuje wywołania cyklu życia i każdy zapisany punkt.

    Z tego samego powodu co `FakeEmbedder`: prawdziwy klient przekracza granicę procesu, a ten
    plik sprawdza KOLEJNOŚĆ i TREŚĆ tego, co robi indekser, a nie to, czy Qdrant to zapisze —
    to sprawdza `stack_qdrant`.
    """

    def __init__(self) -> None:
        """
        Description:
        Buduje stub z pustymi zapisami.

        Example args:
            (brak)

        Example result:
            FakeTickets zapisujący do `calls` i `points`
        """
        self.calls:  list[str]         = []
        self.points: list[TicketPoint] = []
        self.name = "tickets"

    async def ensure(self) -> bool:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            True
        """
        self.calls.append("ensure")

        return True

    async def upsert(self, points: list[TicketPoint]) -> int:
        """
        Description:
        Zapisuje paczkę i zgłasza ją jako zapisaną.

        Example args:
            points=[TicketPoint(point_id="df3b…", …)]

        Example result:
            1
        """
        self.calls.append(f"upsert:{len(points)}")
        self.points.extend(points)

        return len(points)

    async def drop(self) -> bool:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            True
        """
        self.calls.append("drop")

        return True

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            None
        """
        self.calls.append("aclose")


def _write(directory: Path, ticket_id: str, **overrides: object) -> None:
    """
    Description:
    Zapisuje jeden artefakt w badanym katalogu.

    Example args:
        directory=Path("/tmp/x")
        ticket_id="33644"
        solution="brak"

    Example result:
        None — plik leży na dysku
    """
    payload = {**VALID_TICKET, "ticket_id": ticket_id, **overrides}

    (directory / f"{ticket_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _indexer(embedder: FakeEmbedder, tickets: FakeTickets) -> TicketsIndexer:
    """
    Description:
    Buduje indekser na dwóch stubach.

    Example args:
        embedder=FakeEmbedder()
        tickets=FakeTickets()

    Example result:
        TicketsIndexer spięty ze stubami
    """
    return TicketsIndexer(embedder=embedder, tickets=tickets)


async def test_good_tickets_are_indexed(tmp_path: Path) -> None:
    """Sprawdza, czy z katalogu z dwoma poprawnymi zgłoszeniami oba trafiają do indeksu (raport
    mówi: wczytano 2, zaindeksowano 2) i czy pierwszą rzeczą, jaką indekser robi z kolekcją, jest
    upewnienie się, że ona istnieje.

    Wyłapuje indekser, który gubi poprawne zgłoszenia albo zaczyna zapisywać punkty do kolekcji,
    której jeszcze nie ma — taki przebieg kończyłby się błędem bazy zamiast zbudowanym
    indeksem."""
    _write(tmp_path, "1")
    _write(tmp_path, "2")

    tickets = FakeTickets()
    report = await _indexer(FakeEmbedder(), tickets).build(tmp_path)

    assert report.read    == 2
    assert report.indexed == 2
    assert tickets.calls[0] == "ensure"


async def test_hollow_tickets_are_dropped_with_a_reason(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie bez wiedzy (w rozwiązaniu i w przyczynie stoi samo „brak") nie
    trafia do indeksu, a raport podaje powód: z dwóch wczytanych zgłoszeń jedno jest
    zaindeksowane, a jedno odrzucone regułą `no_resolution`.

    Wyłapuje dwie usterki: puste zgłoszenie w indeksie, które przy wyszukiwaniu wygląda na
    odpowiedź, oraz odrzucenie bez podanego powodu, którego nie da się odróżnić od błędu
    w czytaniu plików."""
    _write(tmp_path, "1")
    _write(tmp_path, "2", solution="brak", cause="brak")

    report = await _indexer(FakeEmbedder(), FakeTickets()).build(tmp_path)

    assert report.read    == 2
    assert report.indexed == 1
    assert report.dropped == 1
    assert report.filtered.by_reason() == {"no_resolution": 1}


async def test_both_named_vectors_are_built(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie dostaje w indeksie oba wektory i czy każdy pochodzi z właściwego
    trybu embeddera: wektor `problem` z trybu passage, wektor `sts` z trybu sts, a punkt niesie
    nazwę modelu z odpowiedzi embeddera. Atrapa embeddera oddaje w każdym trybie inne liczby,
    więc zamianę widać.

    Wyłapuje wektory zamienione miejscami albo brak jednego z nich. Zamiany nie widać po fakcie,
    bo oba wektory dalej wyglądają poprawnie, a brakujący wektor oznaczałby później ponowną
    indeksację całego korpusu. Wyłapuje też punkt z modelem innym niż ten, który policzył
    wektory: kolekcja nie umiałaby wtedy odmówić mieszania modeli."""
    _write(tmp_path, "1")

    embedder = FakeEmbedder()
    tickets  = FakeTickets()

    await _indexer(embedder, tickets).build(tmp_path)

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
    _write(tmp_path, "1")

    embedder = FakeEmbedder()

    await _indexer(embedder, FakeTickets()).build(tmp_path)

    assert embedder.passage_batches == embedder.sts_batches


async def test_two_models_in_one_batch_stop_the_build(tmp_path: Path) -> None:
    """Sprawdza, czy indeksacja kończy się błędem konfiguracji `EmbeddingConfigError`, który
    nazywa oba modele, i niczego nie zapisuje, gdy embedder policzył wektory `problem` i `sts`
    tej samej paczki dwoma różnymi modelami.

    Wyłapuje indekser, który bierze model z jednego wywołania i nie patrzy na drugie: punkt
    zapisałby jeden model przy wektorze `sts` policzonym innym, a tego nie wykryje już nic."""
    _write(tmp_path, "1")

    tickets = FakeTickets()

    with pytest.raises(EmbeddingConfigError, match=OTHER_MODEL):
        await _indexer(FakeEmbedder(sts_model=OTHER_MODEL), tickets).build(tmp_path)

    assert tickets.points == []


async def test_embedding_text_comes_from_the_model(tmp_path: Path) -> None:
    """Sprawdza, czy tekst wysyłany do embeddera zawiera opis problemu i objawy zgłoszenia,
    a nie zawiera rozwiązania.

    Wyłapuje rozwiązanie, które trafiło do wektora: szukamy zgłoszeń o podobnym problemie,
    a wektor z domieszką odpowiedzi mieszałby podobieństwo problemu z podobieństwem
    rozwiązania."""
    _write(tmp_path, "1")

    embedder = FakeEmbedder()

    await _indexer(embedder, FakeTickets()).build(tmp_path)

    sent = embedder.passage_batches[0][0]

    assert VALID_TICKET["problem"]  in sent
    assert VALID_TICKET["symptoms"] in sent
    assert VALID_TICKET["solution"] not in sent


async def test_large_corpus_is_embedded_in_batches(tmp_path: Path) -> None:
    """Sprawdza, czy przy liczbie zgłoszeń o pięć większej, niż mieści jedna paczka, indekser
    woła embedder więcej niż raz, paczki razem niosą tyle tekstów, ile jest zgłoszeń, i wszystkie
    zgłoszenia są zaindeksowane.

    Wyłapuje dwie usterki: cały korpus wysłany jednym żądaniem, przez co jedno przekroczenie
    czasu kładzie cały przebieg, oraz zgłoszenia zgubione albo powtórzone na granicy paczek."""
    count = EMBED_BATCH_SIZE + 5

    for number in range(count):
        _write(tmp_path, f"{number:04d}")

    embedder = FakeEmbedder()
    report   = await _indexer(embedder, FakeTickets()).build(tmp_path)

    assert report.indexed == count
    assert len(embedder.passage_batches) > 1
    assert sum(len(batch) for batch in embedder.passage_batches) == count


async def test_rebuild_drops_the_collection_first(tmp_path: Path) -> None:
    """Sprawdza, czy pełna odbudowa indeksu najpierw kasuje kolekcję, a dopiero potem zakłada ją
    od nowa.

    Wyłapuje odbudowę, która nie kasuje starej kolekcji: punkty zgłoszeń, których w katalogu już
    nie ma, zostałyby pod spodem i dalej wracały w wynikach wyszukiwania."""
    _write(tmp_path, "1")

    tickets = FakeTickets()

    await _indexer(FakeEmbedder(), tickets).rebuild(tmp_path)

    assert tickets.calls[0] == "drop"
    assert tickets.calls[1] == "ensure"


async def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    """Sprawdza, czy dwie odbudowy z tego samego katalogu dają punkty o tych samych
    identyfikatorach — identyfikator punktu wynika z numeru zgłoszenia.

    Wyłapuje identyfikatory nadawane losowo albo zależne od przebiegu: ponowna indeksacja
    dokładałaby wtedy drugi komplet punktów, zamiast nadpisać pierwszy."""
    _write(tmp_path, "1")
    _write(tmp_path, "2")

    first  = FakeTickets()
    second = FakeTickets()

    await _indexer(FakeEmbedder(), first).rebuild(tmp_path)
    await _indexer(FakeEmbedder(), second).rebuild(tmp_path)

    assert [p.point_id for p in first.points] == [p.point_id for p in second.points]


async def test_missing_directory_is_an_error(tmp_path: Path) -> None:
    """Sprawdza, czy wskazanie katalogu, którego nie ma, kończy się błędem `NotADirectoryError`.

    Wyłapuje indekser, który przy literówce w ścieżce kończy pracę bez błędu, z zerem zgłoszeń —
    pusty przebieg wyglądałby wtedy na udany."""
    with pytest.raises(NotADirectoryError):
        await _indexer(FakeEmbedder(), FakeTickets()).build(tmp_path / "nie-ma")


async def test_empty_directory_indexes_nothing(tmp_path: Path) -> None:
    """Sprawdza, czy pusty katalog daje pusty raport (wczytano 0, zaindeksowano 0), a nie
    wyjątek.

    Wyłapuje indekser, który wywraca się, gdy nie ma czego indeksować. Co zrobić z pustym
    wynikiem, decyduje komenda, która indekser wywołała, więc musi dostać raport."""
    report = await _indexer(FakeEmbedder(), FakeTickets()).build(tmp_path)

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
        _write(tmp_path, f"{number:04d}")

    report = await _indexer(FakeEmbedder(), FakeTickets()).build(tmp_path)

    assert report.warnings


async def test_aclose_closes_the_embedder_and_the_collection() -> None:
    """Sprawdza, czy zamknięcie indeksera zamyka i embedder, i kolekcję.

    Wyłapuje połączenie zostawione otwarte: kto trzyma sam indekser, na przykład komenda,
    sprząta jednym wywołaniem i nie ma jak zamknąć reszty osobno."""
    embedder = FakeEmbedder()
    tickets  = FakeTickets()

    await _indexer(embedder, tickets).aclose()

    assert embedder.closed
    assert tickets.calls == ["aclose"]


def test_indexer_takes_clients_it_does_not_build() -> None:
    """Sprawdza, czy indekser da się zbudować z podanego embeddera i podanej kolekcji — tu
    z prawdziwą klasą kolekcji i adresem, z którym test się nie łączy.

    Wyłapuje konstruktor, który przestał przyjmować gotowych klientów albo przy budowie sam
    sięga po sieć: indekser zależałby wtedy od działającej usługi, a testy z tego pliku nie
    mogłyby podstawić atrap."""
    tickets = TicketsCollection(
        client      = QdrantClient(base_url="http://qdrant:6333"),
        name        = "tickets",
        vector_size = VECTOR_SIZE,
    )
    indexer = TicketsIndexer(embedder=FakeEmbedder(), tickets=tickets)

    assert indexer is not None
