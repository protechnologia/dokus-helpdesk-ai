import json
from pathlib import Path

import pytest

from app.retrieval import VECTOR_PROBLEM, VECTOR_STS, QdrantClient, TicketPoint
from app.service.rag_indexer import EMBED_BATCH_SIZE, TicketIndexer

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
    Stands in for `EmbeddingClient`, returning a vector per text and recording which MODE each
    batch was sent in.

    A stub rather than the production fake: `FakeEncoder` lives on the other side of the HTTP
    boundary (inside the `embedder` service), so there is no offline double for the client itself.
    What matters here is that indexing calls passage and sts separately — a swap between them is
    invisible afterwards, because both vectors still look valid.
    """

    def __init__(self) -> None:
        """
        Description:
        Builds the stub with empty call logs.

        Example args:
            (none)

        Example result:
            FakeEmbedder with `passage_batches` and `sts_batches` empty
        """
        self.passage_batches: list[list[str]] = []
        self.sts_batches:     list[list[str]] = []
        self.closed = False

    async def embed_passage(self, texts: list[str]) -> list[list[float]]:
        """
        Description:
        Records the batch and returns one recognisable vector per text.

        Example args:
            texts=["Wysyłka przez ePUAP…"]

        Example result:
            [[1.0, 1.0, 1.0, 1.0]]
        """
        self.passage_batches.append(texts)

        return [[1.0] * VECTOR_SIZE for _ in texts]

    async def embed_sts(self, texts: list[str]) -> list[list[float]]:
        """
        Description:
        Records the batch and returns a vector distinguishable from the passage one, so a swapped
        pair shows up in the assertions.

        Example args:
            texts=["Wysyłka przez ePUAP…"]

        Example result:
            [[2.0, 2.0, 2.0, 2.0]]
        """
        self.sts_batches.append(texts)

        return [[2.0] * VECTOR_SIZE for _ in texts]

    async def aclose(self) -> None:
        """
        Description:
        Marks the stub closed.

        Example args:
            (none)

        Example result:
            None
        """
        self.closed = True


class FakeQdrant:
    """
    Description:
    Stands in for `QdrantClient`, recording collection lifecycle calls and every point written.

    Same reasoning as `FakeEmbedder`: the real client crosses a process boundary, and what this
    file tests is the ORDER and CONTENT of what the indexer does, not whether Qdrant stores it —
    that is covered by `integration_qdrant`.
    """

    def __init__(self) -> None:
        """
        Description:
        Builds the stub with empty logs.

        Example args:
            (none)

        Example result:
            FakeQdrant recording into `calls` and `points`
        """
        self.calls:  list[str]        = []
        self.points: list[TicketPoint] = []
        self.collection = "tickets"

    async def ensure_collection(self, vector_size: int) -> bool:
        """
        Description:
        Records the call and the size it was asked for.

        Example args:
            vector_size=4

        Example result:
            True
        """
        self.calls.append(f"ensure:{vector_size}")

        return True

    async def upsert_points(self, points: list[TicketPoint]) -> int:
        """
        Description:
        Records the batch and reports it as written.

        Example args:
            points=[TicketPoint(point_id="df3b…", …)]

        Example result:
            1
        """
        self.calls.append(f"upsert:{len(points)}")
        self.points.extend(points)

        return len(points)

    async def delete_collection(self) -> bool:
        """
        Description:
        Records the call.

        Example args:
            (none)

        Example result:
            True
        """
        self.calls.append("delete")

        return True


def _write(directory: Path, ticket_id: str, **overrides: object) -> None:
    """
    Description:
    Writes one artifact into the directory under test.

    Example args:
        directory=Path("/tmp/x")
        ticket_id="33644"
        solution="brak"

    Example result:
        None — the file exists on disk
    """
    payload = {**VALID_TICKET, "ticket_id": ticket_id, **overrides}

    (directory / f"{ticket_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _indexer(embedder: FakeEmbedder, qdrant: FakeQdrant) -> TicketIndexer:
    """
    Description:
    Builds the indexer over the two stubs.

    Example args:
        embedder=FakeEmbedder()
        qdrant=FakeQdrant()

    Example result:
        TicketIndexer wired to the stubs
    """
    return TicketIndexer(embedder=embedder, qdrant=qdrant, vector_size=VECTOR_SIZE)


async def test_good_tickets_are_indexed(tmp_path: Path) -> None:
    """Directory of usable artifacts → every one becomes a point, and the collection is ensured
    before anything is written."""
    _write(tmp_path, "1")
    _write(tmp_path, "2")

    qdrant = FakeQdrant()
    report = await _indexer(FakeEmbedder(), qdrant).build(tmp_path)

    assert report.read    == 2
    assert report.indexed == 2
    assert qdrant.calls[0] == f"ensure:{VECTOR_SIZE}"


async def test_hollow_tickets_are_dropped_with_a_reason(tmp_path: Path) -> None:
    """Artifact the quality filter rejects → not indexed, and the report names why. A drop with no
    reason is indistinguishable from a bug in the reader."""
    _write(tmp_path, "1")
    _write(tmp_path, "2", solution="brak", cause="brak")

    report = await _indexer(FakeEmbedder(), FakeQdrant()).build(tmp_path)

    assert report.read    == 2
    assert report.indexed == 1
    assert report.dropped == 1
    assert report.filtered.by_reason() == {"no_resolution": 1}


async def test_both_named_vectors_are_built(tmp_path: Path) -> None:
    """Each ticket → a point carrying BOTH named vectors, each from its own mode. Building only
    one now would make adding the other a full re-index later, and a swapped pair is undetectable
    afterwards because both still look like valid vectors."""
    _write(tmp_path, "1")

    embedder = FakeEmbedder()
    qdrant   = FakeQdrant()

    await _indexer(embedder, qdrant).build(tmp_path)

    point = qdrant.points[0]

    assert point.vector_problem == [1.0] * VECTOR_SIZE  # from embed_passage
    assert point.vector_sts     == [2.0] * VECTOR_SIZE  # from embed_sts
    assert point.to_qdrant()["vector"].keys() == {VECTOR_PROBLEM, VECTOR_STS}


async def test_both_modes_receive_the_same_text(tmp_path: Path) -> None:
    """Passage and sts embed the SAME text — the two vectors describe one record, so a difference
    here would mean the record is findable as one thing and comparable as another."""
    _write(tmp_path, "1")

    embedder = FakeEmbedder()

    await _indexer(embedder, FakeQdrant()).build(tmp_path)

    assert embedder.passage_batches == embedder.sts_batches


async def test_embedding_text_comes_from_the_model(tmp_path: Path) -> None:
    """Embedded text is `ParsedTicket.embedding_text()` → problem and symptoms, never `solution`.
    A vector polluted with the answer mixes the two signals we search by."""
    _write(tmp_path, "1")

    embedder = FakeEmbedder()

    await _indexer(embedder, FakeQdrant()).build(tmp_path)

    sent = embedder.passage_batches[0][0]

    assert VALID_TICKET["problem"]  in sent
    assert VALID_TICKET["symptoms"] in sent
    assert VALID_TICKET["solution"] not in sent


async def test_large_corpus_is_embedded_in_batches(tmp_path: Path) -> None:
    """More tickets than one batch → several embedder calls, together carrying every ticket once.
    One giant request would put the whole run at the mercy of a single timeout."""
    count = EMBED_BATCH_SIZE + 5

    for number in range(count):
        _write(tmp_path, f"{number:04d}")

    embedder = FakeEmbedder()
    report   = await _indexer(embedder, FakeQdrant()).build(tmp_path)

    assert report.indexed == count
    assert len(embedder.passage_batches) > 1
    assert sum(len(batch) for batch in embedder.passage_batches) == count


async def test_rebuild_drops_the_collection_first(tmp_path: Path) -> None:
    """rebuild() → delete precedes ensure; otherwise the old points would survive underneath."""
    _write(tmp_path, "1")

    qdrant = FakeQdrant()

    await _indexer(FakeEmbedder(), qdrant).rebuild(tmp_path)

    assert qdrant.calls[0] == "delete"
    assert qdrant.calls[1] == f"ensure:{VECTOR_SIZE}"


async def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    """Two rebuilds in a row → the same points, because ids derive from `ticket_id`. This is what
    makes a rebuild replace the corpus instead of duplicating it."""
    _write(tmp_path, "1")
    _write(tmp_path, "2")

    first  = FakeQdrant()
    second = FakeQdrant()

    await _indexer(FakeEmbedder(), first).rebuild(tmp_path)
    await _indexer(FakeEmbedder(), second).rebuild(tmp_path)

    assert [p.point_id for p in first.points] == [p.point_id for p in second.points]


async def test_missing_directory_is_an_error(tmp_path: Path) -> None:
    """Path that is not a directory → NotADirectoryError, never an empty successful run."""
    with pytest.raises(NotADirectoryError):
        await _indexer(FakeEmbedder(), FakeQdrant()).build(tmp_path / "nie-ma")


async def test_empty_directory_indexes_nothing(tmp_path: Path) -> None:
    """Empty directory → an empty report rather than a crash; the CLI decides what that means."""
    report = await _indexer(FakeEmbedder(), FakeQdrant()).build(tmp_path)

    assert report.read    == 0
    assert report.indexed == 0


async def test_silent_filter_is_reported(tmp_path: Path) -> None:
    """Corpus large enough to judge, with nothing dropped → the report carries a warning. This is
    how a filter that stopped matching announces itself, since the rules cannot notice their own
    silence."""
    for number in range(60):
        _write(tmp_path, f"{number:04d}")

    report = await _indexer(FakeEmbedder(), FakeQdrant()).build(tmp_path)

    assert report.warnings


def test_indexer_takes_clients_it_does_not_build() -> None:
    """Indexer is constructed from clients handed to it → the domain never reaches for a URL or an
    SDK of its own (rule 4), which is what lets these tests run without either service."""
    indexer = TicketIndexer(
        embedder    = FakeEmbedder(),
        qdrant      = QdrantClient(base_url="http://qdrant:6333", collection="tickets"),
        vector_size = VECTOR_SIZE,
    )

    assert indexer is not None
