"""
Description:
Silnik `agent` (p. 19.5): uruchamia graf anonimizacji (`agent_graphs/anonymize/`) — wzorce
zamieniają dane o stałym kształcie, a model anonimizujący wskazuje osoby i adresy, których
wzorce nie łapią. Model tekstu nie przepisuje — oddaje fragmenty, a każdą zamianę robi kod — więc
nie może zgubić ani zmienić wiedzy, która w zgłoszeniu stoi.

Przykład (zmyślony):

    przed: „Od: Bogumił Cieślak <b.cieslak@ug.pl>\\nPani Halino, mieszkanka z Wierzbowej 6 w Kutnie
            prosi o kontakt pod 600 100 200.”
    po:    „Od: {IMIĘ} {NAZWISKO} <{EMAIL}>\\nPani {IMIĘ}, mieszkanka z {ADRES} prosi o kontakt
            pod {TELEFON}.”

O czym pamiętać przy zmianach:

- Kroki, ich kolejność i to, co który robi, opisuje graf; silnik tylko go uruchamia i zapisuje
  przebieg do logu usługi, wpis po wpisie, same liczby.
- Awaria modelu w którymkolwiek węźle to `LLMError` i 503: tekstu bez węzła osób nie oddaje się
  dalej (fail-closed).
"""

import logging

from langgraph.graph.state import CompiledStateGraph

from anonymizer_app.agent_graphs.anonymize.graph import build_agent_graph
from anonymizer_app.agent_graphs.anonymize.state import AnonymizeState
from anonymizer_app.core_engine.base import Engine
from anonymizer_app.engine_llm import LLMClient

logger = logging.getLogger(__name__)

# Nazwa silnika w odpowiedzi i w `ANONYMIZATION_ENGINE`. `api` przyjmuje wynik każdego silnika
# poza atrapą, więc ta nazwa nie jest częścią kontraktu — tylko `fake` nim jest.
AGENT_ENGINE_NAME = "agent"


class AgentEngine(Engine):
    """
    Description:
    Prawdziwy silnik usługi (`ANONYMIZATION_ENGINE=agent`): graf anonimizacji na kliencie modelu.

    Flow:
        1. Fabryka buduje go z klientem modelu, po sprawdzeniu, że prompt mieści się w oknie.
        2. Konstruktor składa graf raz; skompilowany graf obsługuje każde żądanie osobnym stanem.
        3. `anonymize()` przepuszcza tekst przez graf, zapisuje jego przebieg do logu i oddaje
           tekst ze znacznikami.
        4. `aclose()` zamyka połączenia z modelem przy wyłączaniu usługi.
    """

    def __init__(
        self,
        llm: LLMClient,  # np. LLMClient(base_url="https://…/v1", model="speakleash/…")
    ):
        """
        Description:
        Buduje silnik i jego graf na podanym kliencie modelu. Z modelem się nie łączy.

        Example args:
            llm=LLMClient(base_url="https://…/v1", model="speakleash/…")

        Example result:
            AgentEngine gotowy do `anonymize()`
        """
        self._llm   = llm
        self._graph = build_agent_graph(llm)

    @property
    def name(self) -> str:
        """
        Description:
        Nazwa silnika w odpowiedzi usługi.

        Example args:
            (brak)

        Example result:
            "agent"
        """
        return AGENT_ENGINE_NAME

    @property
    def model(self) -> str | None:
        """
        Description:
        Nazwa modelu anonimizującego, z którym rozmawia klient silnika.

        Example args:
            (brak)

        Example result:
            "speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic"
        """
        return self._llm.model

    @property
    def graph(self) -> CompiledStateGraph:
        """
        Description:
        Graf, na którym działa silnik — dla testów i pomiarów, które czytają stan końcowy.

        Example args:
            (brak)

        Example result:
            CompiledStateGraph(…)
        """
        return self._graph

    async def anonymize(
        self,
        text: str,  # np. "Od: Bogumił Cieślak <b.cieslak@ug.pl>\nPani Halino…"
    ) -> str:
        """
        Description:
        Przepuszcza tekst przez graf anonimizacji i oddaje tekst ze znacznikami.

        Example args:
            text="Od: Bogumił Cieślak <b.cieslak@ug.pl>\\nPani Halino, proszę o kontakt."

        Example result:
            "Od: {IMIĘ} {NAZWISKO} <{EMAIL}>\\nPani {IMIĘ}, proszę o kontakt."

        Raises:
            EngineConfigError: serwer modelu odrzucił klucz albo nie zna modelu
            LLMError: model nie odpowiedział albo odpowiedział spoza schematu
        """
        final = await self.run_graph(text)

        # Przebieg wpis po wpisie: nazwa węzła i liczby, nigdy tekst.
        for entry in final.log:
            logger.info("anonymize_step node=%s %s", entry.node, entry.message)

        self._log_call(text, final.output)

        return final.output

    async def run_graph(
        self,
        text: str,  # np. "Od: Bogumił Cieślak <b.cieslak@ug.pl>…"
    ) -> AnonymizeState:
        """
        Description:
        Przepuszcza tekst przez graf i oddaje stan końcowy: wynik każdego węzła i przebieg.
        LangGraph zwraca słownik pól, a wołający czyta je z modelu stanu.

        Example args:
            text="Od: Bogumił Cieślak <b.cieslak@ug.pl>"

        Example result:
            AnonymizeState(input_text="Od: Bogumił…", output="Od: {IMIĘ} {NAZWISKO} <{EMAIL}>",
                           persons=[…], addresses=[], log=[LogEntry(…), …])

        Raises:
            EngineConfigError: serwer modelu odrzucił klucz albo nie zna modelu
            LLMError: model nie odpowiedział albo odpowiedział spoza schematu
        """
        result = await self._graph.ainvoke(AnonymizeState(input_text=text))

        final = AnonymizeState(**result)

        return final

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia z modelem.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._llm.aclose()
