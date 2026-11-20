"""
Description:
Atrapy i składanie serwisu masowego importu (`TicketsImporter`) do testów: plik eksportu
w kształcie, który wytwarza `scripts/export_raw_tickets.py`, atrapa modelu, która na każde
zgłoszenie odpowiada kartą, i serwis importu na grafie `parse_ticket` z węzłów właściwych. Używają
ich testy serwisu importu i komendy `helpdesk tickets import`.

| funkcja / klasa  | do czego                                                                 |
|------------------|--------------------------------------------------------------------------|
| `write_export()` | kładzie w `raw-db/` korpusu testu plik eksportu jednego zgłoszenia       |
| `CardLLM`        | atrapa modelu: kartą na każde zgłoszenie, błędem na wskazane numery      |
| `importer_on()`  | serwis importu na korpusie testu, z prawdziwymi węzłami grafu karty      |
| `StubImporter`   | atrapa serwisu do testów komendy: melduje podane raporty                 |
| `StubImporterFactory` | atrapa fabryki serwisu: zapisuje argumenty, oddaje `StubImporter`   |
"""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from app.agent_graphs import parse_ticket
from app.agent_graphs.factory import build_real_graph
from app.agent_nodes.agent import tool_call_turn
from app.config import Settings
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_model.tickets.tickets_import_report import TicketsImportReport
from app.core_service.importer_tickets import TicketsImporter
from app.core_service.loader_dict_resolution import get_resolution_classes
from app.core_service.normalizer_ticket_mail import MailNormalizer
from app.engine_anonymization import Anonymizer
from app.engine_llm import (
    ChatMessage,
    LLMClient,
    LLMCompletion,
    LLMError,
    LLMTurn,
    LLMUsage,
    ToolDefinition,
)
from tests._helpers.mail import SAFE_MAIL_DIR
from tests._helpers.tickets_import.constants import COST_PER_TICKET, MODEL
from tests._helpers.tickets_index.samples import PERSON, sample_card

# Numer zgłoszenia z pierwszej linii wątku `RawTicket.as_thread()`: „ZGŁOSZENIE 41002 z …”.
TICKET_ID_IN_THREAD = re.compile(r"ZGŁOSZENIE (\S+)")


def write_export(
    root:      Path,                 # np. tmp_path — katalog korpusu testu
    ticket_id: int,                  # np. 41002
    status:    str = "rozwiazany",   # np. "w_weryfikacji" — sprawa w toku
    category:  str = "Błąd",         # np. "Automat mailowy"
) -> Path:
    """
    Description:
    Kładzie w `raw-db/` korpusu testu plik eksportu jednego zmyślonego zgłoszenia, w kształcie
    z `scripts/export_raw_tickets.py`. Komentarz konsultanta niesie zmyśloną osobę, po której
    widać, czy do modelu i korpusu poszedł tekst po anonimizacji.

    Example args:
        root=Path("/tmp/pytest-0/korpus")
        ticket_id=41002
        status="rozwiazany"
        category="Błąd"

    Example result:
        Path("/tmp/pytest-0/korpus/raw-db/zgloszenie-41002.json")
    """
    payload = {
        "zrodlo":     "mysql_helpdesk_20260826-131135.sql",
        "tabela":     "zgloszenie",
        "zgloszenie": {
            "id":               ticket_id,
            "created_at":       "2026-08-20 09:30:00",
            "status":           status,
            "kategoria":        category,
            "czego_dotyczy":    "Brak przesyłek z e-Doręczeń",
            "szczegolowy_opis": "<p>Od wczoraj nie przychodzą przesyłki z e-Doręczeń.</p>",
        },
        "komentarze": [
            {
                "id":         ticket_id * 10,
                "typ":        "rozwiazanie",
                "autor_rola": "konsultant",
                "created_at": "2026-08-20 11:00:00",
                "tresc":      f"<p>Wznowiono kolejkę odbioru, potwierdziła {PERSON}.</p>",
            },
        ],
    }

    path = TicketsCorpus(root=root).raw_db_dir / f"zgloszenie-{ticket_id}.json"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    return path


class CardLLM(LLMClient):
    """
    Description:
    Atrapa modelu do testów importu: na każdą turę odpowiada narzędziem odpowiedzi grafu karty,
    z polami przykładowej karty bez tych, które dokłada graf, więc numer i datę karty bierze ze
    stanu. Dla numerów z `failures` zgłasza podany wyjątek. Zapisuje turę użytkownika każdego
    wywołania — po niej widać, co poszło do modelu.

    Stub, a nie `FakeLLMClient`: tamta atrapa ma skończony scenariusz tur, a import przepuszcza
    przez jeden graf dowolnie wiele zgłoszeń.
    """

    def __init__(
        self,
        cards:    Mapping[str, dict[str, Any]] | None = None,  # np. {"41003": {"useful": False}}
        failures: Mapping[str, Exception] | None      = None,  # np. {"41004": LLMError("…")}
    ) -> None:
        """
        Description:
        Zapamiętuje zmiany pól karty i wyjątki na numer zgłoszenia, z pustym dziennikiem tur.

        Example args:
            cards={"41003": {"useful": False, "useful_reason": "Formułka zamykająca."}}
            failures={"41004": LLMError("model nie odpowiedział")}

        Example result:
            CardLLM z pustym `prompts`
        """
        self.prompts:   list[str] = []
        self._cards    = dict(cards or {})
        self._failures = dict(failures or {})

    async def complete(
        self,
        prompt: str,                # np. "…"
        system: str | None = None,  # np. None
    ) -> LLMCompletion:
        """
        Description:
        Import tej metody nie woła; wywołanie znaczy, że graf karty zmienił drogę do modelu.

        Example args:
            prompt="…"

        Example result:
            (zawsze wyjątek)

        Raises:
            LLMError: zawsze
        """
        raise LLMError("CardLLM odpowiada tylko turami z narzędziami")

    async def complete_turn(
        self,
        system:   str,                       # np. "Jesteś parserem zgłoszeń helpdesku…"
        messages: Sequence[ChatMessage],     # np. [ChatMessage(role="user", content="…")]
        tools:    Sequence[ToolDefinition],  # np. [ToolDefinition(name="respond_parse_ticket", …)]
    ) -> LLMTurn:
        """
        Description:
        Zapisuje turę użytkownika i odpowiada kartą zgłoszenia, którego numer stoi w wątku, albo
        zgłasza wyjątek przypisany do tego numeru.

        Example args:
            system="Jesteś parserem zgłoszeń helpdesku…"
            messages=[ChatMessage(role="user", content="…ZGŁOSZENIE 41002 z 2026-08-20…")]
            tools=[ToolDefinition(name="respond_parse_ticket", …)]

        Example result:
            LLMTurn(message=ChatMessage(role="assistant", tool_calls=[…]), model="model-testowy", …)

        Raises:
            Exception: wyjątek przypisany do numeru zgłoszenia w `failures`
        """
        prompt    = messages[0].content
        ticket_id = TICKET_ID_IN_THREAD.search(prompt).group(1)

        self.prompts.append(prompt)

        if ticket_id in self._failures:
            raise self._failures[ticket_id]

        card      = sample_card(ticket_id=ticket_id, **self._cards.get(ticket_id, {}))
        arguments = card.model_dump(mode="json", exclude=set(parse_ticket.FILLED_BY_GRAPH))

        turn = LLMTurn(
            message    = tool_call_turn(parse_ticket.RESPOND_TOOL_NAME, arguments),
            model      = MODEL,
            latency_ms = 1.0,
            usage      = LLMUsage(calls=1, cost_usd=COST_PER_TICKET),
        )

        return turn


def importer_on(
    root:        Path,        # np. tmp_path — katalog korpusu testu
    llm:         LLMClient,   # np. CardLLM()
    anonymizer:  Anonymizer,  # np. ReplacingAnonymizer(PERSON, PERSON_MARKERS)
    concurrency: int = 2,     # np. 1 — gdy test patrzy na kolejność
) -> TicketsImporter:
    """
    Description:
    Buduje serwis importu na korpusie testu, z grafem karty z węzłów właściwych — tą samą funkcją
    fabryki grafów co fabryka serwisu — na podanym modelu i anonimizatorze. Wątki kanału
    „Automat mailowy” czyści słownikiem zmyślonym z `data/safe/mail/`.

    Example args:
        root=Path("/tmp/pytest-0/korpus")
        llm=CardLLM()
        anonymizer=ReplacingAnonymizer("Anna Nowak", "{IMIĘ} {NAZWISKO}")
        concurrency=2

    Example result:
        TicketsImporter czytający `raw-db/` korpusu testu
    """
    graph = build_real_graph(
        graph          = parse_ticket,
        llm            = llm,
        anonymizer     = anonymizer,
        tools          = (),
        limits         = {},
        max_iterations = 20,
    )

    importer = TicketsImporter(
        corpus      = TicketsCorpus(root=root),
        graph       = graph,
        anonymizer  = anonymizer,
        normalizer  = MailNormalizer(SAFE_MAIL_DIR),
        vocabulary  = get_resolution_classes(),
        model       = MODEL,
        concurrency = concurrency,
    )

    return importer


class StubImporter:
    """
    Description:
    Zastępuje `TicketsImporter` w testach komendy: melduje podane raporty po kolei i oddaje
    ostatni albo zgłasza podany wyjątek. Zapisuje limit każdego przebiegu i to, czy serwis
    zamknięto.

    Stub, bo test komendy sprawdza jej kontrakt — co wypisuje i jakim kodem kończy — a prawdziwy
    serwis potrzebowałby modelu i anonimizatora.
    """

    def __init__(
        self,
        reports: Sequence[TicketsImportReport] = (),    # np. [sample_import_report(), …]
        error:   BaseException | None          = None,  # np. NotADirectoryError("…")
    ) -> None:
        """
        Description:
        Zapamiętuje raporty do meldowania albo wyjątek, z pustym dziennikiem limitów.

        Example args:
            reports=[sample_import_report(parsed=0), sample_import_report(parsed=25)]
            error=None

        Example result:
            StubImporter z pustym `limits`, niezamknięty
        """
        self.limits: list[int | None] = []
        self.closed   = False
        self._reports = list(reports)
        self._error   = error

    async def run(
        self,
        limit:       int | None,                             # np. 20
        on_progress: Callable[[TicketsImportReport], None],  # drukowanie postępu w komendzie
    ) -> TicketsImportReport:
        """
        Description:
        Zapisuje limit i melduje raporty po kolei albo zgłasza podany wyjątek.

        Example args:
            limit=20
            on_progress=_print_progress

        Example result:
            TicketsImportReport(todo=25, parsed=25, …) — ostatni z podanych

        Raises:
            BaseException: wyjątek podany w konstruktorze
        """
        self.limits.append(limit)

        if self._error is not None:
            raise self._error

        for report in self._reports:
            on_progress(report)

        return self._reports[-1]

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje, że serwis zamknięto.

        Example args:
            (brak)

        Example result:
            None
        """
        self.closed = True


class StubImporterFactory:
    """
    Description:
    Zastępuje fabrykę serwisu importu w testach komendy: zapisuje, z jakim korpusem i liczbą
    zgłoszeń naraz komenda ją zawołała, i oddaje atrapę serwisu z `importer` albo zgłasza
    `build_error`.
    """

    def __init__(self) -> None:
        """
        Description:
        Buduje zapis bez wywołań, z atrapą serwisu bez raportów i bez błędu budowy.

        Example args:
            (brak)

        Example result:
            StubImporterFactory z pustymi `corpora` i `concurrency`
        """
        self.importer:    StubImporter        = StubImporter()
        self.corpora:     list[TicketsCorpus] = []
        self.concurrency: list[int]           = []
        self.build_error: Exception | None    = None

    def build(
        self,
        settings:    Settings,       # np. Settings()
        corpus:      TicketsCorpus,  # np. TicketsCorpus(root=Path("/tmp/x"))
        concurrency: int,            # np. 4
    ) -> StubImporter:
        """
        Description:
        Zapisuje korpus i liczbę zgłoszeń naraz i oddaje atrapę serwisu albo zgłasza błąd budowy.

        Example args:
            settings=Settings()
            corpus=TicketsCorpus(root=Path("/tmp/x"))
            concurrency=4

        Example result:
            StubImporter z `importer`

        Raises:
            Exception: `build_error`, gdy test go ustawił
        """
        self.corpora.append(corpus)
        self.concurrency.append(concurrency)

        if self.build_error is not None:
            raise self.build_error

        return self.importer
