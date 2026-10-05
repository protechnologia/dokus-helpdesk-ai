import asyncio

import pytest

from app.agent_graphs import run_graph, search
from app.agent_nodes.agent import AgentNode
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools import AgentTool
from app.agent_tools.docs.find_docs_text.fake import FakeFindDocsTextTool
from app.agent_tools.docs.find_docs_vector.fake import FakeFindDocsVectorTool
from app.agent_tools.docs.list_docs.fake import FakeListDocsTool
from app.agent_tools.docs.read_docs.fake import FakeReadDocsTool
from app.agent_tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.agent_tools.tickets.read_tickets_card.fake import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_thread.fake import FakeReadTicketsThreadTool
from app.config import LLMSettings, Settings
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import get_llm_client
from tests.conftest import live_generation_llm

pytestmark = pytest.mark.llm_live

# Cała pętla agenta na prawdziwym modelu generującym z konfiguracji (`LLM_GENERATION_*`): węzły
# właściwe `agent` i `run_tools` w grafie `search`, z promptem i opisami narzędzi produktu.
# Narzędzia to atrapy na zmyślonym materiale, anonimizator to atrapa (zgłoszenie jest zmyślone),
# a odpowiedź ustawia atrapa `respond`. Testy sprawdzają to, czego nie pokaże ani atrapa modelu,
# ani test jednej tury: czy prawdziwy model przechodzi pętlę od zgłoszenia do odpowiedzi, czyli
# czy dostawca przyjmuje rozmowę rosnącą z tury na turę, a model trafia w nasze narzędzia.
#
# KOSZTUJE: jeden przebieg pliku to jedna sprawa w pętli — kilka tur modelu z promptem i ośmioma
# narzędziami (rząd kilku centów na mocnym modelu), policzona raz i wspólna dla wszystkich testów.

# Dostawca self-hosted: nasz sprzęt nie nalicza tokenów, więc koszt sprawy to zero.
PROVIDER_SELFHOSTED = "ollama"


def fake_tools() -> list[AgentTool]:
    """
    Description:
    Atrapy wszystkich ośmiu narzędzi agenta, w kolejności z `TOOL_NAMES` grafu — te same, które
    model widziałby w produkcie, tylko na zmyślonym materiale.

    Example args:
        (brak)

    Example result:
        [FakeFindTicketsVectorTool(), FakeFindTicketsTextTool(), FakeReadTicketsCardTool(), …]
    """
    tools = [
        FakeFindTicketsVectorTool(),
        FakeFindTicketsTextTool(),
        FakeReadTicketsCardTool(),
        FakeReadTicketsThreadTool(),
        FakeListDocsTool(),
        FakeFindDocsVectorTool(),
        FakeFindDocsTextTool(),
        FakeReadDocsTool(),
    ]

    return tools


async def _run_the_search_loop(
    llm: LLMSettings,  # np. Settings().llm_generation()
) -> search.SearchState:
    """
    Description:
    Składa graf `search` tak, jak zrobi to fabryka — te same narzędzia, limity wywołań i limit
    tur z konfiguracji dla węzłów `agent` i `run_tools` — i przepuszcza przez niego przykładowe
    zgłoszenie na prawdziwym modelu. To jedyne miejsce w pliku, które woła model.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)

    Example result:
        SearchState(sources=[SourceRef(item_id="90001", …), …], iterations=4,
                    usage=LLMUsage(calls=4, cost_usd=0.021, …), …)

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział w czasie albo oddał turę nie do użycia
    """
    settings = Settings()
    tools    = fake_tools()
    limits   = settings.tool_call_limits()

    graph = search.build_graph(
        anonymize      = AnonymizeNode(FakeAnonymizer()),
        agent          = AgentNode(
            llm           = get_llm_client(llm),
            system_prompt = search.system_prompt(),
            user_prompt   = search.user_prompt,
            tools         = search.model_tools(tools, limits),
        ),
        run_tools      = RunToolsNode(tools, limits),
        respond        = FakeRespondNode(search.SearchDone()),
        max_iterations = settings.agent_max_iterations,
    )

    return await run_graph(graph, search.example_state())


@pytest.fixture(scope="module")
def final(
    request: pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
) -> search.SearchState:
    """
    Description:
    Stan końcowy jednej sprawy przeprowadzonej na prawdziwym modelu, policzony raz na plik
    (`_run_the_search_loop()`). Konfigurację bierze przez `live_generation_llm()`, które odmawia,
    gdy testy wybrano bez jawnego `llm_live` albo gdy modelem jest atrapa.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        SearchState(sources=[…], iterations=4, usage=LLMUsage(calls=4, …), …)
    """
    return asyncio.run(_run_the_search_loop(live_generation_llm(request.config)))


def test_the_model_ends_the_run_with_the_respond_tool(final: search.SearchState) -> None:
    """Sprawdza, czy prawdziwy model kończy sprawę sam, wywołaniem narzędzia odpowiedzi
    `respond_search`, zanim wyczerpie limit tur: ostatnia tura modelu to to wywołanie, a ostatnim
    krokiem przebiegu jest `respond`.

    Wyłapuje pętlę, którą ucina dopiero limit tur, oraz model, który nie umie zakończyć rozmowy
    naszym narzędziem: sprawa kosztowałaby wtedy maksimum i nie miała wyniku."""
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert [call.name for call in model_turns[-1].tool_calls] == [search.RESPOND_TOOL_NAME]
    assert final.log[-1].node == "respond"
    assert final.iterations   <  Settings().agent_max_iterations


def test_every_model_turn_calls_a_tool(final: search.SearchState) -> None:
    """Sprawdza, czy każda tura prawdziwego modelu w tej sprawie jest wywołaniem narzędzia, a nie
    samym tekstem.

    Wyłapuje model, który w środku pętli odpowiada tekstem zamiast narzędziem: taka tura kończy
    pętlę bez wyniku, więc wymuszenie wywołania narzędzia u dostawcy musi działać."""
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert model_turns
    assert all(turn.tool_calls for turn in model_turns)


def test_the_model_reads_what_it_found(final: search.SearchState) -> None:
    """Sprawdza, czy sprawa kończy się listą źródeł: model nie tylko wyszukał materiał, ale też
    odczytał choć jedno zgłoszenie albo sekcję dokumentacji.

    Wyłapuje pętlę, w której model szuka i od razu kończy albo w której wyniki naszych narzędzi
    do niego nie docierają: wyszukiwanie wróciłoby wtedy bez żadnego źródła."""
    assert final.sources
    assert {ref.source for ref in final.sources} <= {"tickets", "docs"}


def test_the_cost_of_the_run_is_the_sum_of_its_turns(final: search.SearchState) -> None:
    """Sprawdza, czy zużycie całej sprawy zgadza się z jej przebiegiem: tyle wywołań modelu, ile
    było tur, policzone tokeny wejścia i wyjścia oraz koszt większy od zera, a przy modelu
    self-hosted równy zeru.

    Wyłapuje koszt sprawy, w którym giną tury z narzędziami: wołający widziałby w odpowiedzi
    ułamek tego, co sprawa naprawdę kosztowała."""
    usage        = final.usage
    input_tokens = usage.prompt_tokens + usage.cache_write_tokens + usage.cache_read_tokens

    assert usage.calls             == final.iterations
    assert input_tokens            > 0
    assert usage.completion_tokens > 0

    if Settings().llm_generation().provider.strip().lower() == PROVIDER_SELFHOSTED:
        assert usage.cost_usd == 0.0
    else:
        assert usage.cost_usd > 0
