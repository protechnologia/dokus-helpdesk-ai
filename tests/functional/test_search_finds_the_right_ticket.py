from collections.abc import AsyncIterator
from datetime import date

import pytest

from app.factory import build_searcher
from app.model.ticket_raw import RawTicket
from app.service.rag_searcher import RagSearcher

pytestmark = pytest.mark.functional

# The product question, not the wiring one: a real ticket goes in, and the record that answers it
# has to come back. Everything is live — the model parses the thread, the embedder builds the
# vector, Qdrant ranks the corpus.
#
# Deliberately OUTSIDE the `integration` umbrella (CLAUDE.md -> "Testy"): this costs an LLM call
# per query and takes as long as the model needs, while a wiring check has to stay cheap enough to
# run on every marked pass. The wiring half is `tests/integration/test_api_search_pipeline.py`,
# which needs no model at all.
#
# Queries are written the way a USER would report the problem — never by copying the record's own
# `problem`. Copying would make the task trivial for any model and the test would stop measuring
# anything: the same rule the golden set is built on, where a query knows only what the reporter
# can see, never the cause nor the vocabulary of the solution. Each case therefore quotes the
# target record verbatim above it, so the distance between the two is reviewable — a query that
# drifts toward the record's own wording makes this file pass while proving less, and that is
# invisible without the original in front of you.

# How far down the list a correct answer still counts. Five, because that is what the product
# shows: RAG_TOP_K feeds the generation prompt, so a record ranked sixth is one nobody sees.
ACCEPTED_RANK = 5

CASES = [
    # Record 32768
    #   problem:  "Backup nie tworzy kopii do katalogu BACKUP_BAZA_ESOD po 12.04.2026."
    #   symptoms: "Kopie zapasowe przestały się wykonywać na maszynie EZD5-backup."
    #   cause:    "Brak połączonego zasobu wymaganego do tworzenia kopii zapasowych."
    # Shares no distinctive term: no "BACKUP_BAZA_ESOD", no machine name, no date.
    pytest.param(
        "Od kilku dni nie robią się kopie zapasowe na serwerze. Nic nie ląduje w katalogu, "
        "a wcześniej wszystko działało.",
        "32768",
        id="kopie-zapasowe",
    ),
    # Record 29657
    #   problem:  "Po zmianie stanowiska w systemie, zniknęły przypisane do użytkownika dokumenty."
    #   symptoms: "Użytkownik nie widzi swoich dokumentów po zmianie stanowiska. Brak komunikatu
    #              błędu."
    #   cause:    "brak"
    # The closest of the three, because the event ("zmiana stanowiska") IS the symptom and a user
    # would name it the same way. Kept because it is honest: not every report can be paraphrased
    # away from the record without describing a different problem.
    pytest.param(
        "Pracownik dostał nowe stanowisko i po tej zmianie nie widzi już swoich pism. "
        "Żadnego błędu nie ma, dokumenty po prostu zniknęły z listy.",
        "29657",
        id="zmiana-stanowiska",
    ),
    # Record 22696
    #   problem:  "Przestało działać zapisywanie skanów w eSOD. Skan działa wybiórczo."
    #   symptoms: "Skany nie docierały do Dokusa przy próbie skanowania wielu stron (testowano na
    #              około 30)."
    #   cause:    "Nałożyły się dwa problemy: przekraczanie limitu PHP wynoszącego 8MB oraz brak
    #              najnowszej wersji aplikacji dokus-offline"
    # The user cannot know the cause here (a PHP limit), which is the point: this is the corpus's
    # own pattern — the symptom repeats, the cause does not.
    pytest.param(
        "Skanowanie przestało działać jak trzeba — przy większej liczbie kartek skan w ogóle "
        "nie dociera do systemu, przy jednej stronie czasem się uda.",
        "22696",
        id="skanowanie",
    ),
]


@pytest.fixture
async def searcher(host_settings) -> AsyncIterator[RagSearcher]:
    """
    Description:
    Yields a searcher built the way the API builds it, pointed at the host-published ports.

    Built through `build_searcher()` rather than assembled here: the point of a functional test is
    to exercise what the product does, and a locally wired service could differ from the shipped
    one in exactly the settings that matter.

    Example args:
        host_settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        RagSearcher over the live model, embedder and collection

    Raises:
        AssertionError: LLM_PROVIDER is `fake` — with a stub this would prove only the wiring,
            which the integration half already covers
    """
    assert host_settings.llm_provider != "fake", (
        "test funkcjonalny wymaga prawdziwego modelu — ustaw LLM_PROVIDER na dostawcę. "
        "Przy atrapie sprawdzałby wyłącznie okablowanie, czyli to, co robi już "
        "tests/integration/test_api_search_pipeline.py"
    )

    searcher = build_searcher(host_settings)

    yield searcher

    await searcher.aclose()


def _raw(text: str) -> RawTicket:
    """
    Description:
    Builds the incoming ticket from what a user wrote.

    Example args:
        text="Od kilku dni nie robią się kopie zapasowe na serwerze."

    Example result:
        RawTicket(ticket_id="functional-test", date=date.today(), body="Od kilku dni…")
    """
    return RawTicket(
        ticket_id = "functional-test",
        date      = date.today(),
        category  = "",
        subject   = "",
        body      = text,
    )


@pytest.mark.parametrize(("query", "expected_ticket_id"), CASES)
async def test_a_user_worded_ticket_finds_its_record(
    searcher:           RagSearcher,
    query:              str,
    expected_ticket_id: str,
) -> None:
    """A ticket described in the reporter's own words → the record that answers it lands in the
    top 5. The whole product in one assertion: parse, embed, rank."""
    result = await searcher.search(_raw(query))

    assert result.hits, "brak trafień — indeks pusty albo próg odciął wszystko"

    found = [hit.ticket_id for hit in result.hits[:ACCEPTED_RANK]]

    assert expected_ticket_id in found, (
        f"oczekiwano zgłoszenia {expected_ticket_id} w top {ACCEPTED_RANK}, "
        f"a wróciły {found}; zapytanie zrozumiane jako: {result.query.problem!r}"
    )


async def test_the_model_rewrites_the_thread_before_searching(searcher: RagSearcher) -> None:
    """The parsed query is a summary, not the raw mail. That rewriting is why the runtime pays for
    an LLM call before searching: greetings, signatures and quoted history pollute the vector."""
    raw = _raw(
        "Dzień dobry,\n\nod kilku dni nie robią się kopie zapasowe na serwerze.\n\n"
        "Pozdrawiam serdecznie\nJan Kowalski\nUrząd Miasta"
    )

    result = await searcher.search(raw)

    assert result.query.problem
    assert result.query.problem != raw.body
