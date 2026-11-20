"""
Description:
Masowy import zgłoszeń do korpusu (p. 31): z eksportu zrzutu bazy w `raw-db/` robi wątki po
anonimizacji i karty grafem `parse_ticket`, tym samym, którym trasa zamknięcia robi kartę
pojedynczego zgłoszenia. Pliki trafiają do `anonymized/` i `cards/` korpusu po każdym zgłoszeniu,
a indeksy buduje z nich potem `helpdesk tickets reindex`. Woła go komenda
`helpdesk tickets import`.

| zgłoszenie w `raw-db/`     | co robi import                             | licznik w raporcie  |
|----------------------------|--------------------------------------------|---------------------|
| w toku (status niekońcowy) | pomija: wątek nie jest skończony           | `skipped_open`      |
| ma już kartę w `cards/`    | pomija: nie płaci drugi raz, nie nadpisuje | `already_carded`    |
| reszta                     | parsuje i zapisuje wątek z kartą           | `parsed` / `failed` |

Wątek z kanału „Automat mailowy” idzie do grafu oczyszczony (`MailNormalizer`, p. 32): bez
drugiej kopii maila, cytatów i stopek, z autorami z podpisów; każdy inny bez zmian.

Przed — plik eksportu ze statusem `rozwiazany` i kategorią „Błąd”:

    data/unsafe/corpus/raw-db/zgloszenie-33644.json

Po — dwa pliki korpusu i raport przebiegu:

    data/unsafe/corpus/anonymized/33644.txt
    data/unsafe/corpus/cards/33644.json
    data/unsafe/corpus/import-2026-11-13T10-15-00.json   (todo=1, parsed=1, cost_usd=0.0052, …)

Co się dzieje po drodze:

1. `_select()` czyta eksport po numerach rosnąco, odsiewa zgłoszenia spoza zakresu i te z kartą,
   a przy limicie bierze pierwsze N z reszty.
2. Wołający dostaje raport z liczbami zakresu, zanim ruszy pierwsze wywołanie modelu.
3. Zgłoszenia idą przez graf po kilka naraz, z wątkiem oczyszczonym, gdy są z kanału
   „Automat mailowy”; każde kończy się zapisem wątku i karty albo wpisem na liście błędów.
4. Po każdym zgłoszeniu wołający dostaje raport z postępem i kosztem.
5. Na końcu, także po przerwaniu, raport trafia do katalogu korpusu.

O czym pamiętać przy zmianach:

- Wznawianie stoi na pomijaniu zgłoszeń z kartą: przerwany przebieg wznawia się tym samym
  poleceniem, a karta z trasy zamknięcia, nowsza niż eksport, nie jest cofana.
- Wątek bez karty (zapis przerwany między plikami) następny przebieg nadpisuje — to jedyny plik
  korpusu, który import nadpisuje.
- Błąd konfiguracji (model, klucz, anonimizator na atrapie silnika, brak słownika maili przy
  zgłoszeniu z kanału „Automat mailowy”) zatrzymuje cały przebieg;
  błąd jednego zgłoszenia trafia na listę błędów, a przebieg idzie dalej — chyba że błędów jest
  10 z rzędu (`MAX_FAILURES_IN_ROW`): to znaczy, że padł pod z anonimizatorem albo dostawca
  modelu, i bez hamulca przebieg przeleciałby przez resztę listy, zapisując same błędy.
- W logu i raporcie stoją tylko numery, liczby i nazwy: przebieg operuje na danych klientów.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs import parse_ticket, run_graph
from app.agent_graphs.parse_ticket import ParseTicketState
from app.core_model.dicts.resolution_vocabulary import ResolutionVocabulary
from app.core_model.tickets.raw_ticket import RawTicket
from app.core_model.tickets.ticket_import_failure import TicketImportFailure
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_model.tickets.tickets_import_report import TicketsImportReport
from app.core_service.normalizer_ticket_mail import MailNormalizer
from app.core_service.parser_ticket_raw import is_closed_in_source, load_raw_ticket
from app.core_service.writer_ticket_card import write_card_with_thread
from app.engine_anonymization import AnonymizationConfigError, AnonymizationError, Anonymizer
from app.engine_llm import LLMConfigError, LLMError

logger = logging.getLogger(__name__)

# Przedrostek nazwy pliku eksportu przed numerem zgłoszenia: `zgloszenie-33644.json`.
EXPORT_PREFIX = "zgloszenie-"

# Co dostaje wołający po wyborze zgłoszeń i po każdym zgłoszeniu: raport z bieżącymi liczbami.
ProgressCallback = Callable[[TicketsImportReport], None]

# Ile zgłoszeń z rzędu może skończyć się błędem, zanim przebieg stanie (decyzja 2026-11-13).
# Pojedyncze błędy to chwilowe awarie; seria znaczy, że padła zależność, a każde następne
# zgłoszenie skończy się tak samo.
MAX_FAILURES_IN_ROW = 10


class TicketsImportAbortedError(Exception):
    """
    Description:
    Przebieg stanął, bo `MAX_FAILURES_IN_ROW` zgłoszeń z rzędu skończyło się błędem: padł pod
    z anonimizatorem albo dostawca modelu. Karty zapisane wcześniej zostają, a to samo polecenie
    wznowi import po naprawie.
    """


class TicketsImporter:
    """
    Description:
    Parsuje zgłoszenia z eksportu zrzutu do korpusu: wątek po anonimizacji i karta na zgłoszenie,
    z raportem postępu i kosztu.

    Do czego:
    Korpus to jedyny drogi przebieg modelu w projekcie (zasada 7), więc import zapisuje każdą kartę
    od razu, wznawia się po przerwaniu i liczy koszt na bieżąco. Serwis nie składa grafu sam: graf
    na modelu i anonimizatorze z konfiguracji podaje fabryka (`factory_tickets_importer.py`),
    a test — graf na atrapach.

    Flow:
        1. `run()` woła `_select()`, który wybiera zgłoszenia i zakłada raport.
        2. `run()` przepuszcza wybrane zgłoszenia przez `_import_one()` po kilka naraz.
        3. `_import_one()` uruchamia graf i woła `_record()` z kartą albo dopisuje błąd.
        4. `_save()` zapisuje raport w katalogu korpusu.
        5. `aclose()` zamyka anonimizator, na którym stoi graf.
    """

    def __init__(
        self,
        corpus:      TicketsCorpus,         # np. Settings().tickets_corpus()
        graph:       CompiledStateGraph,    # np. build_real_graph(parse_ticket, …)
        anonymizer:  Anonymizer,            # ten, na którym stoi graf; zamyka go `aclose()`
        normalizer:  MailNormalizer,        # np. MailNormalizer(Path("/code/data/unsafe/mail"))
        vocabulary:  ResolutionVocabulary,  # np. get_resolution_classes()
        model:       str,                   # np. "gpt-6.1-sol" — do raportu
        concurrency: int,                   # np. 4 — ile zgłoszeń naraz
    ):
        """
        Description:
        Spina serwis z korpusem, grafem karty, czyszczeniem wątków mailowych i słownikiem
        rozstrzygnięć. Graf i anonimizator są wstrzykiwane: serwis nie składa klientów sam
        (zasada 4).

        Example args:
            corpus=TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
            graph=build_real_graph(parse_ticket, llm=…, anonymizer=…, tools=(), …)
            anonymizer=AnonymizerClient(base_url="http://anonymizer:8000")
            normalizer=MailNormalizer(Path("/code/data/unsafe/mail"))
            vocabulary=get_resolution_classes()
            model="gpt-6.1-sol"
            concurrency=4

        Example result:
            TicketsImporter czytający `raw-db/` i piszący do `anonymized/` i `cards/`
        """
        self._corpus      = corpus
        self._graph       = graph
        self._anonymizer  = anonymizer
        self._normalizer  = normalizer
        self._vocabulary  = vocabulary
        self._model       = model
        self._concurrency = concurrency

        # Ile zgłoszeń z rzędu skończyło się błędem; zeruje je każda zapisana karta.
        self._failures_in_row = 0

    async def run(
        self,
        limit:       int | None,        # np. 20 — próba na pierwszych; None = wszystkie
        on_progress: ProgressCallback,  # np. drukowanie postępu w komendzie
    ) -> TicketsImportReport:
        """
        Description:
        Parsuje zgłoszenia z eksportu, które są w zakresie i nie mają jeszcze karty. Raport oddaje
        wołającemu raz po wyborze zgłoszeń i potem po każdym zgłoszeniu, a na końcu zapisuje go
        w katalogu korpusu, jeśli było co robić.

        Example args:
            limit=None
            on_progress=lambda report: print(report.done)

        Example result:
            TicketsImportReport(files=1955, todo=1758, parsed=1756, failed=[…], cost_usd=9.12, …)

        Raises:
            NotADirectoryError: korpus nie ma katalogu `raw-db/`
            LLMConfigError: model generujący jest źle skonfigurowany
            AnonymizationConfigError: anonimizator odmówił z powodu konfiguracji
            TicketsImportAbortedError: `MAX_FAILURES_IN_ROW` zgłoszeń z rzędu skończyło się błędem
        """
        todo, report = self._select(limit)

        self._failures_in_row = 0

        on_progress(report)

        # --- nic do zrobienia: bez raportu na dysku ---
        if not todo:
            return report

        gate  = asyncio.Semaphore(self._concurrency)
        tasks = [
            asyncio.create_task(self._import_one(raw, report, gate, on_progress))
            for raw in todo
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            # Przy błędzie konfiguracji albo przerwaniu reszta zgłoszeń nie rusza, a raport mówi,
            # co zdążyło się zrobić.
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

            report.finished_at = datetime.now(UTC)
            self._save(report)

        return report

    async def aclose(self) -> None:
        """
        Description:
        Zamyka anonimizator, na którym stoi graf. Sprzątający woła tylko to.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._anonymizer.aclose()

    def _select(
        self,
        limit: int | None,  # np. 20
    ) -> tuple[list[RawTicket], TicketsImportReport]:
        """
        Description:
        Czyta eksport po numerach rosnąco i wybiera zgłoszenia do sparsowania: zamknięte w źródle
        i bez karty w korpusie; przy limicie pierwsze N z nich. Zakłada raport z liczbami
        zakresu.

        Example args:
            limit=None

        Example result:
            ([RawTicket(ticket_id="4832", …), …],
             TicketsImportReport(files=1955, skipped_open=61, already_carded=1758, todo=136, …))

        Raises:
            NotADirectoryError: korpus nie ma katalogu `raw-db/`
        """
        raw_dir = self._corpus.raw_db_dir

        if not raw_dir.is_dir():
            raise NotADirectoryError(f"brak katalogu eksportu zgłoszeń: {raw_dir}")

        paths  = sorted(raw_dir.glob(f"{EXPORT_PREFIX}*.json"), key=_ticket_number)
        counts = {"open": 0, "carded": 0}
        todo:  list[RawTicket] = []

        for path in paths:
            # --- w toku: wątek nie jest skończony, przyjdzie trasą zamknięcia ---
            if not is_closed_in_source(path):
                counts["open"] += 1
                continue

            raw = load_raw_ticket(path)

            # --- karta już jest: z wcześniejszego przebiegu albo z trasy zamknięcia ---
            if (self._corpus.cards_dir / f"{raw.ticket_id}.json").exists():
                counts["carded"] += 1
                continue

            todo.append(raw)

        if limit is not None:
            todo = todo[:limit]

        report = TicketsImportReport(
            started_at     = datetime.now(UTC),
            model          = self._model,
            prompt_digest  = parse_ticket.prompt_digest(),
            files          = len(paths),
            skipped_open   = counts["open"],
            already_carded = counts["carded"],
            todo           = len(todo),
        )

        return todo, report

    async def _import_one(
        self,
        raw:         RawTicket,            # np. RawTicket(ticket_id="33644", …)
        report:      TicketsImportReport,  # raport przebiegu, uzupełniany na bieżąco
        gate:        asyncio.Semaphore,    # ogranicza, ile zgłoszeń idzie naraz
        on_progress: ProgressCallback,     # np. drukowanie postępu w komendzie
    ) -> None:
        """
        Description:
        Parsuje jedno zgłoszenie grafem karty i zapisuje wątek z kartą; zgłoszenie z kanału
        „Automat mailowy” idzie do grafu oczyszczone. Błąd zgłoszenia dopisuje do raportu bez
        treści i liczy, ile błędów było z rzędu. Potem oddaje raport wołającemu.

        Example args:
            raw=RawTicket(ticket_id="33644", …)
            report=TicketsImportReport(todo=1758, …)
            gate=asyncio.Semaphore(4)
            on_progress=lambda report: print(report.done)

        Example result:
            None — pliki `anonymized/33644.txt` i `cards/33644.json` w korpusie

        Raises:
            LLMConfigError: model generujący jest źle skonfigurowany
            AnonymizationConfigError: anonimizator odmówił z powodu konfiguracji
            MailDictionaryConfigError: zgłoszenie jest z kanału mailowego, a słownika maili nie ma
            TicketsImportAbortedError: tym zgłoszeniem seria błędów doszła do `MAX_FAILURES_IN_ROW`
        """
        async with gate:
            state = parse_ticket.STATE(
                input_text = self._normalizer.normalize(raw).as_thread(),
                ticket_id  = raw.ticket_id,
                date       = raw.date,
                vocabulary = self._vocabulary,
            )

            try:
                final = await run_graph(self._graph, state)
            # --- konfiguracja: czekanie nic nie da, cały przebieg staje ---
            except (LLMConfigError, AnonymizationConfigError):
                raise
            # --- jedno zgłoszenie: numer i nazwa błędu, bez treści; przebieg idzie dalej ---
            except (LLMError, AnonymizationError) as exc:
                failure = TicketImportFailure(ticket_id=raw.ticket_id, error=type(exc).__name__)

                report.failed.append(failure)
                logger.warning("import ticket_id=%s error=%s", raw.ticket_id, failure.error)

                self._failures_in_row += 1
            else:
                self._record(report, final)

                self._failures_in_row = 0

            on_progress(report)

            # --- seria błędów: padła zależność, następne zgłoszenia skończą się tak samo ---
            if self._failures_in_row >= MAX_FAILURES_IN_ROW:
                raise TicketsImportAbortedError(
                    f"{self._failures_in_row} zgłoszeń z rzędu skończyło się błędem (ostatni: "
                    f"{report.failed[-1].error}) — sprawdź anonimizator i model; to samo "
                    "polecenie wznowi import"
                )

    def _record(
        self,
        report: TicketsImportReport,  # raport przebiegu, uzupełniany na bieżąco
        final:  ParseTicketState,     # stan końcowy grafu `parse_ticket`
    ) -> None:
        """
        Description:
        Zapisuje wątek po anonimizacji i kartę ze stanu końcowego grafu i dolicza je do raportu:
        kartę, jej ocenę przydatności, koszt i wartość pola `component`.

        Example args:
            report=TicketsImportReport(parsed=0, …)
            final=ParseTicketState(anonymized=AnonymizedText(…), output=ParsedTicket(…), …)

        Example result:
            None — `report.parsed` większe o 1, pliki zgłoszenia w korpusie
        """
        card = final.output

        write_card_with_thread(self._corpus, final.anonymized, card)

        report.parsed   += 1
        report.useful   += card.useful
        report.cost_usd += final.usage.cost_usd
        report.components[card.component] = report.components.get(card.component, 0) + 1

        logger.info(
            "import ticket_id=%s useful=%s cost_usd=%.6f",
            card.ticket_id,
            card.useful,
            final.usage.cost_usd,
        )

    def _save(
        self,
        report: TicketsImportReport,  # np. TicketsImportReport(parsed=1756, …)
    ) -> None:
        """
        Description:
        Zapisuje raport przebiegu w katalogu korpusu, pod nazwą z chwilą startu.

        Example args:
            report=TicketsImportReport(started_at=datetime(2026, 11, 13, 10, 15, …), …)

        Example result:
            None — plik `import-2026-11-13T10-15-00.json` w korpusie
        """
        path = self._corpus.import_report_path(report.started_at)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _ticket_number(
    path: Path,  # np. Path("…/raw-db/zgloszenie-33644.json")
) -> int:
    """
    Description:
    Zwraca numer zgłoszenia z nazwy pliku eksportu, żeby pliki szły po numerach, a nie po
    kolejności napisów („zgloszenie-4832” przed „zgloszenie-10012”).

    Example args:
        path=Path("data/unsafe/corpus/raw-db/zgloszenie-33644.json")

    Example result:
        33644
    """
    return int(path.stem.removeprefix(EXPORT_PREFIX))
