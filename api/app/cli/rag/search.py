import asyncio
from datetime import date

import typer

from app.config import Settings
from app.embedding import EmbeddingError
from app.factory import build_searcher
from app.llm import LLMError
from app.model.rag_search_result import SearchResult
from app.model.ticket_raw import RawTicket
from app.retrieval import RetrievalError
from app.service.rag_searcher import SearchParseError

HELP = "Znajdź zgłoszenia podobne do podanej treści."


def _print_hits(
    result: SearchResult,  # np. SearchResult(query=ParsedTicket(…), hits=[TicketHit(…)])
) -> None:
    """
    Description:
    Wypisuje, co znalazło wyszukiwanie: jak odczytano zapytanie, potem trafienia ze score.

    Odczyt zapytania idzie PIERWSZY i bezwarunkowo. Dziwną listę trafień znacznie częściej
    tłumaczy nieoczekiwane odczytanie zgłoszenia niż samo wyszukiwanie, a w terminalu ten odczyt
    byłby inaczej niewidoczny.

    Example args:
        result=SearchResult(query=ParsedTicket(…), hits=[TicketHit(score=0.87, …)])

    Example result:
        None — trafienia na stdout
    """
    query = result.query

    typer.echo("")
    typer.echo("Zapytanie zrozumiane jako:")
    typer.echo(f"  problem:   {query.problem}")
    typer.echo(f"  objawy:    {query.symptoms}")
    typer.echo(f"  komponent: {query.component}")

    # Pusty wynik to ODPOWIEDŹ, nie porażka: „nowy typ problemu" jest poprawny dla dużej części
    # korpusu, więc mówimy to wprost, zamiast zostawić ciszę.
    if result.is_empty:
        typer.echo("\nBrak trafień — nowy typ problemu.")

        # Bez tego operator nie odróżni pustego indeksu od progu, który wszystko wyciął.
        if result.dropped_below_threshold:
            typer.echo(
                f"({result.dropped_below_threshold} trafień odrzucono progiem RAG_SCORE_MIN)"
            )

        return

    typer.echo(f"\nZnaleziono {len(result.hits)}:")

    for hit in result.hits:
        payload = hit.payload

        typer.echo(f"\n  [{hit.score:.3f}] zgłoszenie {hit.ticket_id} ({payload.get('date', '')})")
        typer.echo(f"      problem:     {payload.get('problem', '')}")
        typer.echo(f"      przyczyna:   {payload.get('cause', '')}")
        typer.echo(f"      rozwiązanie: {payload.get('solution', '')}")

    if result.dropped_below_threshold:
        typer.echo(f"\nOdrzucono progiem: {result.dropped_below_threshold}")


async def _run_search(
    text: str,  # np. "Nie mogę wysłać pisma przez ePUAP"
) -> SearchResult:
    """
    Description:
    Wykonuje jedno wyszukiwanie i zwalnia potem połączenia.

    Serwis pochodzi z `build_searcher()` w `factory.py` — jedna droga składania, więc CLI nie może
    po cichu szukać z innymi parametrami niż skonfigurowane. Budowany na przebieg i zamykany po
    nim; `POST /search` już go nie używa (idzie przez graf `search` od p. 6).

    Example args:
        text="Nie mogę wysłać pisma przez ePUAP"

    Example result:
        SearchResult(query=ParsedTicket(…), hits=[TicketHit(score=0.87, …)])

    Raises:
        SearchParseError: odpowiedź modelu nie przeszła walidacji jako zgłoszenie
        LLMError: zawiódł sam dostawca
        EmbeddingError: embedder nieosiągalny albo odpowiedział błędem
        RetrievalError: Qdrant nieosiągalny albo odpowiedział błędem
    """
    searcher = build_searcher(Settings())

    # Zapytanie z konsoli nie ma numeru ani wątku, więc id mówi, skąd przyszło, a data to dziś.
    # Oba przechodzą do artefaktu nietknięte przez model, więc rozpoznawalny znacznik jest lepszy
    # niż zmyślony numer.
    raw = RawTicket(
        ticket_id = "cli",
        date      = date.today(),
        category  = "",
        subject   = "",
        body      = text,
    )

    try:
        return await searcher.search(raw)
    finally:
        await searcher.aclose()


def search_tickets(
    text: str = typer.Argument(..., help="Treść nowego zgłoszenia."),
) -> None:
    """
    Description:
    `helpdesk rag search` — szuka w indeksie zgłoszeń podobnych do podanej treści, parsując ją
    tym samym promptem, którym sparsowano korpus.

    Kosztuje jedno wywołanie LLM na przebieg — zapytanie jest parsowane przed embedowaniem, bo
    surowy mail niesie powitania i podpisy, które zaszumiają wektor.

    Example args:
        text="Nie mogę wysłać pisma przez ePUAP, błąd komunikacji"

    Example result:
        wypisuje odczyt zapytania i trafienia; kod 0 także wtedy, gdy nic nie znaleziono

    Raises:
        typer.Exit: kod 2 przy nieosiągalnej zależności albo nieczytelnym zapytaniu
    """
    try:
        result = asyncio.run(_run_search(text))
    except SearchParseError as exc:
        # Kod 2, jak przy nieosiągalnej usłudze: oba znaczą „ten przebieg nie umiał odpowiedzieć",
        # w odróżnieniu od „korpus nic nie ma" — co jest poprawnym wynikiem z kodem 0.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except (LLMError, EmbeddingError, RetrievalError) as exc:
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    _print_hits(result)
