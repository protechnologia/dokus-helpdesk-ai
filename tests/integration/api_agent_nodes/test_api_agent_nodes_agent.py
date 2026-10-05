import importlib
import pkgutil
from types import ModuleType

import pytest
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

import app.agent_graphs
from app.agent_graphs import run_graph, search
from app.agent_graphs.fake import FAKE_MAX_ITERATIONS, FAKE_READ_ARGUMENTS, FAKE_SEARCH_ARGUMENTS
from app.agent_nodes.agent import AgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import FakeRunToolsNode
from app.agent_tools.docs.find_docs_text.fake import FakeFindDocsTextTool
from app.agent_tools.docs.find_docs_vector.fake import FakeFindDocsVectorTool
from app.agent_tools.docs.list_docs.fake import FakeListDocsTool
from app.agent_tools.docs.read_docs.fake import FakeReadDocsTool
from app.agent_tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.agent_tools.tickets.read_tickets_card.fake import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_thread.fake import FakeReadTicketsThreadTool
from app.config import Settings
from app.engine_anonymization import AnonymizedText, FakeAnonymizer
from app.engine_llm import ChatMessage, FakeLLMClient

# Prawdziwy węzeł agenta wpięty w grafy i uruchomiony przez LangGraph. Model to atrapa, która
# oddaje zaplanowane tury; wykonanie narzędzi i odpowiedź to też atrapy. Te testy sprawdzają to,
# czego nie widać w teście samego węzła: czy w każdym grafie model dostaje prompt i narzędzia tego
# grafu i czy rozmowa dociera do niego w całości, gdy między turami przechodzi przez stan grafu.

GRAPHS = [
    importlib.import_module(f"app.agent_graphs.{module.name}")
    for module in pkgutil.iter_modules(app.agent_graphs.__path__)
    if module.ispkg
]

# Każde narzędzie agenta, jakie dziś istnieje — test wybiera z nich dozwolone dla grafu.
AGENT_TOOLS = [
    FakeFindTicketsVectorTool(),
    FakeFindTicketsTextTool(),
    FakeReadTicketsCardTool(),
    FakeReadTicketsThreadTool(),
    FakeListDocsTool(),
    FakeFindDocsVectorTool(),
    FakeFindDocsTextTool(),
    FakeReadDocsTool(),
]

# Limity wywołań narzędzi, jakie daje konfiguracja domyślna.
LIMITS = Settings(_env_file=None).tool_call_limits()

# Element, który dostawca każe odesłać w następnej turze — tu zmyślony.
REASONING = {"type": "reasoning", "id": "rs_1", "encrypted_content": "gAAAAB…"}


def name_of(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_close>
) -> str:
    """
    Description:
    Nazwa grafu = nazwa jego katalogu.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        "gate_close"
    """
    return graph.__name__.split(".")[-1]


async def fake_output(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_close>
) -> BaseModel:
    """
    Description:
    Wynik w typie grafu, wzięty z przebiegu jego atrapy — żeby atrapa `respond` miała co oddać
    w każdym grafie, bez listy typów w teście.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        Verdict(verdict="pass", reasons=["fake-gate-close-verdict"], …)
    """
    final = await run_graph(graph.build_fake_graph(), graph.example_state())

    return final.output


async def graph_with_agent(
    graph:          ModuleType,                 # np. <module app.agent_graphs.search>
    llm:            FakeLLMClient,              # np. FakeLLMClient(turns=[…])
    max_iterations: int = FAKE_MAX_ITERATIONS,  # np. 2 — limit tur modelu
) -> CompiledStateGraph:
    """
    Description:
    Graf z węzłem właściwym `agent` na podanej atrapie modelu. Prompt i narzędzia węzeł bierze
    z pakietu grafu, tak jak zrobi to fabryka; `run_tools` (tylko w grafach z narzędziami wiedzy)
    i `respond` to atrapy.

    Example args:
        graph=<module app.agent_graphs.search>
        llm=FakeLLMClient(turns=[tool_call_turn("respond_search", {})])
        max_iterations=10

    Example result:
        CompiledStateGraph: anonymize → agent (właściwy) ⇄ run_tools → respond
    """
    tools = [tool for tool in AGENT_TOOLS if tool.name in graph.TOOL_NAMES]
    nodes = {
        "anonymize": AnonymizeNode(FakeAnonymizer()),
        "agent":     AgentNode(
            llm           = llm,
            system_prompt = graph.system_prompt(),
            user_prompt   = graph.user_prompt,
            tools         = graph.model_tools(tools, LIMITS),
        ),
        "respond":   FakeRespondNode(await fake_output(graph)),
    }

    # --- graf bez narzędzi wiedzy: jedna tura, bez pętli ---
    if not graph.TOOL_NAMES:
        return graph.build_graph(**nodes)

    # --- graf z narzędziami: pętla z atrapą `run_tools` i limitem tur ---
    return graph.build_graph(
        **nodes,
        run_tools      = FakeRunToolsNode(result_text='{"tickets": []}'),
        max_iterations = max_iterations,
    )


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
async def test_the_model_gets_the_prompt_and_tools_of_its_graph(graph: ModuleType) -> None:
    """Sprawdza, czy w każdym grafie model dostaje to, co do tego grafu należy: jego prompt
    systemowy, zgłoszenie w wersji po anonimizacji i dokładnie te narzędzia, które graf pozwala
    widzieć, z narzędziem odpowiedzi na końcu.

    Wyłapuje graf, w którym węzeł agenta dostał cudzy prompt albo narzędzie spoza listy — na
    przykład bramkę, która mogłaby sięgnąć do bazy zgłoszeń, choć ma działać bez niej."""
    llm      = FakeLLMClient(turns=[tool_call_turn(graph.RESPOND_TOOL_NAME, {})])
    compiled = await graph_with_agent(graph, llm)
    state    = graph.example_state()

    await run_graph(compiled, state)

    anonymized = state.model_copy(update={"anonymized": AnonymizedText(text=state.input_text)})
    call       = llm.turn_calls[0]

    assert call.system   == graph.system_prompt()
    assert call.messages == [ChatMessage(role="user", content=graph.user_prompt(anonymized))]
    assert [tool.name for tool in call.tools] == [*graph.TOOL_NAMES, graph.RESPOND_TOOL_NAME]


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
async def test_a_run_with_the_real_agent_ends_with_an_output(graph: ModuleType) -> None:
    """Sprawdza, czy każdy graf z prawdziwym węzłem agenta dochodzi do wyniku, gdy model odpowie
    od razu: przebieg to anonimizacja, jedna tura modelu i odpowiedź, a w rozmowie zostaje
    zgłoszenie i tura modelu.

    Wyłapuje graf, do którego węzeł agenta nie pasuje: zwraca coś, czego graf nie umie zapisać
    w stanie, albo po odpowiedzi modelu przebieg nie dochodzi do końca."""
    llm   = FakeLLMClient(turns=[tool_call_turn(graph.RESPOND_TOOL_NAME, {})])
    final = await run_graph(await graph_with_agent(graph, llm), graph.example_state())

    assert final.output is not None
    assert [entry.node for entry in final.log]          == ["anonymize", "agent", "respond"]
    assert [message.role for message in final.messages] == ["user", "assistant"]
    assert (final.iterations, final.usage.calls)        == (1, 1)


async def test_the_conversation_grows_through_the_state_between_turns() -> None:
    """Sprawdza, czy w każdej kolejnej turze model dostaje całą dotychczasową rozmowę: zgłoszenie,
    swoje wcześniejsze wywołania narzędzi i ich wyniki, w tej kolejności. Model tu szuka, czyta
    i odpowiada, więc tury są trzy.

    Wyłapuje wiadomość zgubioną albo powtórzoną między turami: model, który nie widzi wyniku
    narzędzia, szukałby tego samego w kółko, a dostawca odrzuca rozmowę z wywołaniem bez
    wyniku."""
    llm = FakeLLMClient(turns=[
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn("read_tickets_card", FAKE_READ_ARGUMENTS, call_id="call_2"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_3"),
    ])

    final = await run_graph(await graph_with_agent(search, llm), search.example_state())
    sent  = [[message.role for message in call.messages] for call in llm.turn_calls]

    assert sent == [
        ["user"],
        ["user", "assistant", "tool"],
        ["user", "assistant", "tool", "assistant", "tool"],
    ]
    assert [entry.node for entry in final.log] == [
        "anonymize", "agent", "run_tools", "agent", "run_tools", "agent", "respond",
    ]
    assert (final.iterations, final.usage.calls) == (3, 3)


async def test_provider_items_survive_the_trip_through_the_state() -> None:
    """Sprawdza, czy to, co dostawca każe odesłać razem z turą modelu (tu zmyślony zapis
    rozumowania), wraca do modelu w następnej turze bez zmian.

    Wyłapuje zgubienie tego elementu po drodze przez stan grafu: prawdziwy dostawca odrzuciłby
    wtedy drugą turę rozmowy, a na atrapie modelu nic by nie padło."""
    searching = tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1")
    llm       = FakeLLMClient(turns=[
        searching.model_copy(update={"provider_items": [REASONING]}),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_2"),
    ])

    await run_graph(await graph_with_agent(search, llm), search.example_state())

    assert llm.turn_calls[1].messages[1].provider_items == [REASONING]


async def test_the_turn_limit_stops_asking_the_model() -> None:
    """Sprawdza, czy przy limicie dwóch tur model jest pytany dokładnie dwa razy, choć za każdym
    razem chce szukać dalej: po drugiej turze narzędzia nie są już wykonywane, a przebieg idzie
    do odpowiedzi.

    Wyłapuje pętlę bez końca: model, który ciągle woła narzędzia, zużywałby tokeny, dopóki ktoś
    nie przerwie żądania."""
    llm = FakeLLMClient(turns=[
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id=f"call_{number}")
        for number in range(1, 6)
    ])

    final = await run_graph(
        await graph_with_agent(search, llm, max_iterations=2),
        search.example_state(),
    )

    assert len(llm.turn_calls) == 2
    assert [entry.node for entry in final.log] == [
        "anonymize", "agent", "run_tools", "agent", "respond",
    ]
