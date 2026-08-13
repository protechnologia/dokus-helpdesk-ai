import logging
from pathlib import Path

from app.embedding import EmbeddingClient
from app.model.filter_quality_report import QualityReport
from app.model.rag_index_report import IndexBuildReport
from app.model.ticket_parsed import ParsedTicket
from app.retrieval import QdrantClient, TicketPoint
from app.service.filter_ticket_quality import drop_rate_warning, filter_tickets

logger = logging.getLogger(__name__)

# How many tickets are embedded per call to the embedder. The whole corpus in one request would
# hold the run hostage to a single timeout, while one ticket per request wastes most of the time on
# HTTP round-trips — the model batches internally and is far faster fed in bulk.
EMBED_BATCH_SIZE = 32


class TicketIndexer:
    """
    Description:
    Builds the Qdrant index from parsed artifacts: read, filter, embed, upsert.

    Do czego:
    The index is a derivative, never the source of truth (rule 8) — everything here must be
    reproducible from `data/parsed/` with one command and WITHOUT calling an LLM (rule 7). That is
    why this service reads artifacts from disk and talks only to the embedder and Qdrant.

    Flow:
        1. `build()` reads every `*.json` in the directory into `ParsedTicket`.
        2. The quality filter splits them into kept and dropped, with a reason per drop.
        3. Kept tickets are embedded in batches — TWICE, once per named vector: `problem` in
           passage mode (what a runtime query is matched against) and `sts` in symmetric mode.
        4. Points are upserted; the report carries counts, reasons and any warnings.

    Both vectors are built on purpose. Stage 3 measured `query→passage` as the better search mode,
    but only for RAW queries — the argument for `sts→sts` was about PARSED ones, an axis that has
    not been measured (CLAUDE.md -> "Embeddingi"). Dropping `sts` now would make re-adding it a
    full re-index.
    """

    def __init__(
        self,
        embedder:    EmbeddingClient,  # e.g. EmbeddingClient(base_url="http://embedder:8000")
        qdrant:      QdrantClient,     # e.g. QdrantClient(base_url="http://qdrant:6333", …)
        vector_size: int,              # e.g. 768 — must match EMBEDDING_VECTOR_SIZE
    ):
        """
        Description:
        Wires the indexer to the two services it needs. Both clients are injected rather than
        built here: the domain never reaches for an SDK or a URL of its own (rule 4).

        Example args:
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            qdrant=QdrantClient(base_url="http://qdrant:6333", collection="tickets")
            vector_size=768

        Example result:
            TicketIndexer ready to build the collection `tickets`
        """
        self._embedder    = embedder
        self._qdrant      = qdrant
        self._vector_size = vector_size

    async def build(
        self,
        directory: Path,  # e.g. Path("data/parsed")
    ) -> IndexBuildReport:
        """
        Description:
        Indexes a directory of artifacts into the collection and returns what it did. Reads as a
        list of steps; the details sit in the private helpers below.

        Example args:
            directory=Path("data/parsed")

        Example result:
            IndexBuildReport(read=200, indexed=171, filtered=QualityReport(…), warnings=[])

        Raises:
            NotADirectoryError: the path does not exist or is not a directory
            RetrievalError: Qdrant is unreachable or rejected the write
            EmbeddingError: the embedder is unreachable or answered with an error
        """
        tickets = self._read(directory)
        report  = filter_tickets(tickets)
        kept    = self._kept_tickets(tickets, report)

        await self._qdrant.ensure_collection(vector_size=self._vector_size)
        indexed = await self._upsert(kept)

        # Counts only: payloads carry ticket content, i.e. customer data, which belongs to DEBUG at
        # most (CLAUDE.md -> "Logi i obserwowalność").
        logger.info(
            "index build collection=%s read=%d indexed=%d dropped=%d",
            self._qdrant.collection,
            len(tickets),
            indexed,
            len(report.dropped),
        )

        warning = drop_rate_warning(report)

        return IndexBuildReport(
            read     = len(tickets),
            indexed  = indexed,
            filtered = report,
            warnings = [warning] if warning else [],
        )

    async def rebuild(
        self,
        directory: Path,  # e.g. Path("data/parsed")
    ) -> IndexBuildReport:
        """
        Description:
        Drops the collection and builds it again from scratch. Safe by design rather than by care:
        the index is rebuildable from `data/parsed/` with this very command (rule 8), so what is
        destroyed is a derivative.

        Its own method rather than a flag on `build()`, because the two differ in what they RISK
        rather than in how they work — and the CLI has to guard one of them behind a confirmation.

        Example args:
            directory=Path("data/parsed")

        Example result:
            IndexBuildReport(read=200, indexed=171, …)

        Raises:
            NotADirectoryError: the path does not exist or is not a directory
            RetrievalError: Qdrant is unreachable or rejected the write
        """
        await self._qdrant.delete_collection()

        return await self.build(directory)

    def _read(
        self,
        directory: Path,  # e.g. Path("data/parsed")
    ) -> list[ParsedTicket]:
        """
        Description:
        Reads every artifact in the directory, in sorted order so two runs over the same corpus
        produce comparable reports.

        A malformed artifact aborts the run rather than being skipped: `helpdesk tickets validate`
        exists to find those first, and quietly indexing 199 of 200 records would leave a gap
        nobody can see afterwards.

        Example args:
            directory=Path("data/parsed")

        Example result:
            [ParsedTicket(ticket_id="10012", …), …]

        Raises:
            NotADirectoryError: the path does not exist or is not a directory
            ValidationError: an artifact does not satisfy the contract
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"nie jest katalogiem: {directory}")

        return [
            ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]

    def _kept_tickets(
        self,
        tickets: list[ParsedTicket],  # e.g. [ParsedTicket(ticket_id="10012", …)]
        report:  QualityReport,       # e.g. QualityReport(verdicts=[…])
    ) -> list[ParsedTicket]:
        """
        Description:
        Selects the tickets the filter kept, preserving the order they were read in.

        The report carries ticket ids rather than the records themselves — deliberately, so the
        filter stays testable without artifacts — which is why the two are matched back up here.

        Example args:
            tickets=[ParsedTicket(ticket_id="10012", …), ParsedTicket(ticket_id="19596", …)]
            report=QualityReport(verdicts=[…])

        Example result:
            [ParsedTicket(ticket_id="10012", …)]
        """
        kept_ids = {verdict.ticket_id for verdict in report.kept}

        return [ticket for ticket in tickets if ticket.ticket_id in kept_ids]

    async def _upsert(
        self,
        tickets: list[ParsedTicket],  # e.g. [ParsedTicket(ticket_id="10012", …)]
    ) -> int:
        """
        Description:
        Embeds the tickets in batches and writes them as points. Returns how many were written.

        Each batch is embedded TWICE — once per named vector — because the two live in different
        vector spaces and mixing them destroys retrieval silently (CLAUDE.md -> "Embeddingi").
        Both calls take the same texts in the same order, so the results zip back onto the tickets
        they came from; `strict=True` turns any length mismatch into an error rather than a
        silently truncated batch.

        Example args:
            tickets=[ParsedTicket(ticket_id="10012", …)]

        Example result:
            1

        Raises:
            EmbeddingError: the embedder is unreachable or returned a different count
            RetrievalError: Qdrant is unreachable or rejected the write
        """
        written = 0

        for start in range(0, len(tickets), EMBED_BATCH_SIZE):
            batch = tickets[start : start + EMBED_BATCH_SIZE]
            # `embedding_text()` lives on the model so indexing and the runtime query cannot build
            # it differently — two call sites assembling it by hand would drift apart in silence.
            texts = [ticket.embedding_text() for ticket in batch]

            problem_vectors = await self._embedder.embed_passage(texts)
            sts_vectors     = await self._embedder.embed_sts(texts)

            points = [
                TicketPoint.from_ticket(
                    ticket         = ticket,
                    vector_problem = problem_vector,
                    vector_sts     = sts_vector,
                )
                for ticket, problem_vector, sts_vector in zip(
                    batch, problem_vectors, sts_vectors, strict=True
                )
            ]

            written += await self._qdrant.upsert_points(points)

        return written
