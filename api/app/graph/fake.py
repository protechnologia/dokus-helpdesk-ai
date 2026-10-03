from pydantic import BaseModel

from app.nodes.agent import FakeAgentNode, tool_call_turn
from app.nodes.run_tools import FakeRunToolsNode
from app.tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool, default_tickets
from app.tools.tickets.find_tickets_vector.models import FindTicketsVectorResult

# Zapytanie, które atrapa agenta wysyła do `find_tickets_vector` — w kształcie korpusu, zmyślone.
FAKE_SEARCH_ARGUMENTS = {
    "problem":  "Nie przychodzą przesyłki z e-Doręczeń",
    "symptoms": "Brak nowych przesyłek w skrzynce, nadawcy potwierdzają wysyłkę",
}


def fake_search_nodes(
    respond_tool_name: str,        # np. "respond_search"
    output:            BaseModel,  # np. Proposal(text="1. Od kiedy…")
) -> tuple[FakeAgentNode, FakeRunToolsNode]:
    """
    Description: Atrapy agenta i narzędzi dla grafu z narzędziami wiedzy: agent najpierw szuka
    `find_tickets_vector`, potem wywołuje narzędzie odpowiedzi z `output` w argumentach; `run_tools`
    odpowiada wbudowanym zestawem `FakeFindTicketsVectorTool` (jeden objaw, trzy przyczyny) —
    tekstem i źródłami z tych samych `render_for_model()` i `cite()`, co atrapa narzędzia.

    Example args:
        respond_tool_name="respond_suggest_questions"
        output=Proposal(text="1. Od kiedy…")

    Example result:
        (FakeAgentNode z dwiema turami, FakeRunToolsNode z trzema źródłami find_tickets_vector)
    """
    finder = FakeFindTicketsVectorTool()
    result = FindTicketsVectorResult(items=default_tickets())

    agent = FakeAgentNode([
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn(respond_tool_name, output.model_dump(), call_id="call_2"),
    ])

    run_tools = FakeRunToolsNode(
        result_text = finder.render_for_model(result),
        sources     = finder.cite(result),
    )

    return agent, run_tools
