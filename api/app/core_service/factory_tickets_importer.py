"""
Description:
Buduje z konfiguracji serwis masowego importu (p. 31): graf `parse_ticket` z węzłów właściwych na
modelu generującym i anonimizatorze z konfiguracji oraz słownik rozstrzygnięć. Graf składa ta sama
funkcja fabryki grafów (`build_real_graph()`), którą trasy dostają graf przy prawdziwym
dostawcy, więc karty z importu i z trasy zamknięcia powstają tą samą drogą.

Do czego:
Komenda `helpdesk tickets import` bierze stąd gotowy serwis, tak jak komendy indeksacji biorą
indekser z fabryki obok — sama nie składa klientów.

O czym pamiętać przy zmianach:

- Przy atrapie modelu generującego (`LLM_GENERATION_PROVIDER=fake`) serwisu nie ma:
  `build_tickets_importer()` odmawia błędem konfiguracji. Atrapa grafu oddaje zawsze tę samą
  zmyśloną kartę, a anonimizator przyjmuje wtedy wynik atrapy silnika, który oddaje tekst bez
  zmian — do korpusu trafiłyby fałszywe karty, a do `anonymized/` dane osobowe.
- Anonimizator powstaje tutaj, a nie raz na proces jak w trasach: komenda żyje jeden przebieg
  i zamyka go przez `TicketsImporter.aclose()`.
- Budowa nie łączy się z niczym — połączenia powstają przy pierwszym zgłoszeniu.
"""

from app.agent_graphs import parse_ticket
from app.agent_graphs.factory import build_real_graph
from app.config import Settings
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.importer_tickets import TicketsImporter
from app.core_service.loader_dict_resolution import get_resolution_classes
from app.core_service.normalizer_ticket_mail import MailNormalizer
from app.engine_anonymization import build_anonymizer
from app.engine_llm import get_llm_client
from app.engine_llm.factory import PROVIDER_FAKE


class TicketsImportConfigError(Exception):
    """
    Description:
    Konfiguracja nie pozwala importować korpusu: model generujący jest atrapą. Komenda kończy się
    kodem 2, zanim wywoła cokolwiek — czekanie tego nie naprawi.
    """


def build_tickets_importer(
    settings:    Settings,       # np. Settings()
    corpus:      TicketsCorpus,  # np. TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
    concurrency: int,            # np. 4 — ile zgłoszeń naraz
) -> TicketsImporter:
    """
    Description:
    Buduje serwis importu na grafie karty z modelu i anonimizatora z konfiguracji. Nie łączy się
    z niczym.

    Example args:
        settings=Settings()
        corpus=TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
        concurrency=4

    Example result:
        TicketsImporter na grafie `parse_ticket` z modelem `gpt-6.1-sol`

    Raises:
        TicketsImportConfigError: model generujący jest atrapą
        LLMConfigError: nieznany dostawca albo brak klucza czy modelu
        AnonymizationConfigError: pusty `ANONYMIZATION_BASE_URL`
    """
    # Wartość z ENV wpisuje człowiek: wielkość liter i spacje czyta się tak jak w fabryce grafów.
    if settings.llm_generation_provider.strip().lower() == PROVIDER_FAKE:
        raise TicketsImportConfigError(
            "korpus przyjmuje tylko karty prawdziwego modelu, a LLM_GENERATION_PROVIDER=fake"
        )

    llm_settings = settings.llm_generation()
    anonymizer   = build_anonymizer(settings)
    graph        = build_real_graph(
        graph          = parse_ticket,
        llm            = get_llm_client(llm_settings),
        anonymizer     = anonymizer,
        tools          = (),
        limits         = settings.tool_call_limits(),
        max_iterations = settings.agent_max_iterations,
    )

    importer = TicketsImporter(
        corpus      = corpus,
        graph       = graph,
        anonymizer  = anonymizer,
        normalizer  = MailNormalizer(settings.tickets_mail_dir),
        vocabulary  = get_resolution_classes(),
        model       = llm_settings.model or "",
        concurrency = concurrency,
    )

    return importer
