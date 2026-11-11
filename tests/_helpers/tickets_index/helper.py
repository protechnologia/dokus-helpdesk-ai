"""
Description:
Atrapy zależności indeksera zgłoszeń i serwisu zamkniętego zgłoszenia: embeddera, kolekcji
zgłoszeń w Qdrancie i tabeli wątków w Postgresie. Każda zapisuje, co dostała, więc test sprawdza
kolejność i treść tego, co serwis robi, bez usług.

| atrapa         | zastępuje           | co zapisuje                                         |
|----------------|---------------------|-----------------------------------------------------|
| `FakeEmbedder` | `EmbeddingClient`   | paczki tekstów w trybie passage i sts               |
| `FakeTickets`  | `TicketsCollection` | wywołania (`ensure`, `upsert`, `delete`…) i punkty  |
| `FakeThreads`  | `TicketsTable`      | wywołania (`create`, `upsert`, `delete`…) i wiersze |

`closed_ticket_indexer_on()` składa na nich serwis zamkniętego zgłoszenia, z prawdziwym
indekserem kart pomiędzy. Do testów trasy `POST /tickets/closed`: `ReplacingAnonymizer`, który
zamienia jeden fragment na znaczniki (po nim widać, który wątek trafił do korpusu),
`card_graph()` — graf karty z atrapą modelu i prawdziwym węzłem `respond` — oraz
`app_closing_tickets()`, aplikacja z atrapą bramki, tym grafem karty i podanym serwisem.
"""

from pathlib import Path

from fastapi import FastAPI
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs import gate_close, parse_ticket
from app.agent_graphs.factory import get_graph_builder
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.core_model.graphs.verdict import Verdict
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.factory_closed_ticket_indexer import get_closed_ticket_indexer
from app.core_service.indexer_closed_ticket import ClosedTicketIndexer
from app.core_service.indexer_tickets import TicketsIndexer
from app.db_postgres import TicketRow
from app.db_qdrant import TicketPoint
from app.engine_anonymization import AnonymizedText, Anonymizer, AnonymizerInfo, FakeAnonymizer
from app.engine_embedding import Embeddings
from app.main import create_app
from tests._helpers.embedding import EMBEDDING_MODEL
from tests._helpers.tickets_index.constants import VECTOR_SIZE


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

    def __init__(
        self,
        upsert_error: Exception | None = None,  # np. DbQdrantError("…") — awaria przy zapisie
    ) -> None:
        """
        Description:
        Buduje stub z pustymi zapisami; z błędem podanym tutaj każdy zapis punktów kończy się
        tym błędem.

        Example args:
            upsert_error=None

        Example result:
            FakeTickets zapisujący do `calls` i `points`
        """
        self.calls:  list[str]         = []
        self.points: list[TicketPoint] = []
        self.name = "tickets"
        self._upsert_error = upsert_error

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
        Zapisuje paczkę i zgłasza ją jako zapisaną, albo zgłasza błąd podany w konstruktorze.

        Example args:
            points=[TicketPoint(point_id="df3b…", …)]

        Example result:
            1

        Raises:
            Exception: błąd podany jako `upsert_error`
        """
        if self._upsert_error is not None:
            raise self._upsert_error

        self.calls.append(f"upsert:{len(points)}")
        self.points.extend(points)

        return len(points)

    async def delete(self, ticket_ids: list[str]) -> None:
        """
        Description:
        Zapisuje wywołanie z usuwanymi numerami.

        Example args:
            ticket_ids=["41002"]

        Example result:
            None
        """
        self.calls.append(f"delete:{','.join(ticket_ids)}")

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


class FakeThreads:
    """
    Description:
    Zastępuje `TicketsTable`: zapisuje wywołania i wiersze, które miały trafić do tabeli wątków.

    Stub, bo atrapa klienta Postgresa z `tests/_helpers/postgres/` zna tylko czytanie i szukanie,
    a tu liczy się, CO serwis zapisuje i usuwa. Że baza przyjmuje te polecenia, sprawdzają testy
    tabeli na stacku.
    """

    def __init__(self) -> None:
        """
        Description:
        Buduje stub z pustymi zapisami.

        Example args:
            (brak)

        Example result:
            FakeThreads zapisujący do `calls` i `rows`
        """
        self.calls: list[str]       = []
        self.rows:  list[TicketRow] = []

    async def create(self) -> None:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            None
        """
        self.calls.append("create")

    async def upsert(self, rows: list[TicketRow]) -> None:
        """
        Description:
        Zapisuje wywołanie i wiersze.

        Example args:
            rows=[TicketRow(ticket_id="41002", …)]

        Example result:
            None
        """
        self.calls.append(f"upsert:{len(rows)}")
        self.rows.extend(rows)

    async def delete(self, ticket_ids: list[str]) -> None:
        """
        Description:
        Zapisuje wywołanie z usuwanymi numerami.

        Example args:
            ticket_ids=["41002"]

        Example result:
            None
        """
        self.calls.append(f"delete:{','.join(ticket_ids)}")

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


def closed_ticket_indexer_on(
    root:    Path,         # np. tmp_path — katalog korpusu testu
    tickets: FakeTickets,  # np. FakeTickets()
    threads: FakeThreads,  # np. FakeThreads()
) -> ClosedTicketIndexer:
    """
    Description:
    Buduje serwis zamkniętego zgłoszenia na katalogu korpusu testu, z prawdziwym indekserem kart
    stojącym na atrapach embeddera i kolekcji oraz z atrapą tabeli wątków.

    Example args:
        root=Path("/tmp/pytest-0/korpus")
        tickets=FakeTickets()
        threads=FakeThreads()

    Example result:
        ClosedTicketIndexer piszący do `/tmp/pytest-0/korpus` i do obu atrap
    """
    indexer = ClosedTicketIndexer(
        corpus  = TicketsCorpus(root=root),
        cards   = TicketsIndexer(embedder=FakeEmbedder(), tickets=tickets),
        threads = threads,
    )

    return indexer


class ReplacingAnonymizer(Anonymizer):
    """
    Description:
    Anonimizator do testów, który zamienia jeden podany fragment na podane znaczniki i zapisuje
    każdy tekst, który dostał.

    Stub, bo `FakeAnonymizer` oddaje tekst bez zmian, więc wątek przed anonimizacją i po niej
    wyglądałyby tak samo i test nie odróżniłby, który z nich trafił do korpusu.
    """

    def __init__(
        self,
        fragment: str,  # np. "Anna Nowak"
        markers:  str,  # np. "{IMIĘ} {NAZWISKO}"
    ) -> None:
        """
        Description:
        Zapamiętuje, co zamieniać i na co, z pustym dziennikiem tekstów.

        Example args:
            fragment="Anna Nowak"
            markers="{IMIĘ} {NAZWISKO}"

        Example result:
            ReplacingAnonymizer z pustym `texts`
        """
        self.texts: list[str] = []
        self._fragment = fragment
        self._markers  = markers

    async def anonymize(
        self,
        text: str,  # np. "…potwierdziła Anna Nowak."
    ) -> AnonymizedText:
        """
        Description:
        Zapisuje tekst i oddaje go z fragmentem zamienionym na znaczniki.

        Example args:
            text="…potwierdziła Anna Nowak."

        Example result:
            AnonymizedText(text="…potwierdziła {IMIĘ} {NAZWISKO}.")
        """
        self.texts.append(text)

        return AnonymizedText(text=text.replace(self._fragment, self._markers))

    async def describe(self) -> AnonymizerInfo:
        """
        Description:
        Przedstawia się jak atrapa anonimizatora.

        Example args:
            (brak)

        Example result:
            AnonymizerInfo(available=True, engine="fake", model=None)
        """
        return await FakeAnonymizer().describe()


def card_graph(
    anonymizer: Anonymizer,    # np. ReplacingAnonymizer("Anna Nowak", "{IMIĘ} {NAZWISKO}")
    card:       ParsedTicket,  # np. sample_card() — pola, które poda atrapa modelu
) -> CompiledStateGraph:
    """
    Description:
    Graf karty z atrapą modelu, która odpowiada polami podanej karty bez pól wypełnianych przez
    graf, i z prawdziwym węzłem `respond`, który dokłada numer, datę, wersję słownika i model ze
    stanu. Atrapa grafu z pakietu oddaje kartę w całości, więc nie pokazałaby, czy trasa włożyła
    do stanu numer i datę zgłoszenia. Graf jest jednorazowy.

    Example args:
        anonymizer=ReplacingAnonymizer("Anna Nowak", "{IMIĘ} {NAZWISKO}")
        card=sample_card()

    Example result:
        CompiledStateGraph, który oddaje kartę z numerem i datą ze stanu
    """
    answer = tool_call_turn(
        parse_ticket.RESPOND_TOOL_NAME,
        card.model_dump(mode="json", exclude=set(parse_ticket.FILLED_BY_GRAPH)),
    )

    graph = parse_ticket.build_graph(
        anonymize = AnonymizeNode(anonymizer),
        agent     = FakeAgentNode([answer]),
        respond   = parse_ticket.respond_node(),
    )

    return graph


def app_closing_tickets(
    corpus:          ClosedTicketIndexer,  # np. closed_ticket_indexer_on(tmp_path, …)
    verdict:         Verdict,              # np. Verdict(verdict="pass") — werdykt atrapy bramki
    card:            ParsedTicket,         # np. sample_card() — pola karty od atrapy modelu
    card_anonymizer: Anonymizer,           # np. ReplacingAnonymizer("Anna Nowak", "{IMIĘ} …")
) -> FastAPI:
    """
    Description:
    Aplikacja, w której trasa `POST /tickets/closed` dostaje atrapę bramki z podanym werdyktem,
    graf karty z `card_graph()` i podany serwis korpusu. Bramka anonimizuje atrapą, która oddaje
    tekst bez zmian, a graf karty podanym anonimizatorem: wątki obu grafów się różnią, więc
    widać, który trafił do korpusu, a po dzienniku podanego anonimizatora — czy graf karty
    ruszył. Każde żądanie buduje oba grafy od nowa, jak fabryka grafów, więc to samo zgłoszenie
    da się zamknąć dwa razy.

    Example args:
        corpus=closed_ticket_indexer_on(tmp_path, FakeTickets(), FakeThreads())
        verdict=Verdict(verdict="pass")
        card=sample_card()
        card_anonymizer=ReplacingAnonymizer("Anna Nowak", "{IMIĘ} {NAZWISKO}")

    Example result:
        FastAPI, której `POST /tickets/closed` pisze do katalogu korpusu testu
    """
    graphs = {
        gate_close:   lambda: gate_close.build_fake_graph(FakeAnonymizer(), verdict),
        parse_ticket: lambda: card_graph(card_anonymizer, card),
    }

    app = create_app()
    app.dependency_overrides[get_graph_builder]         = lambda: lambda module: graphs[module]()
    app.dependency_overrides[get_closed_ticket_indexer] = lambda: corpus

    return app
