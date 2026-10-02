from pydantic import BaseModel

from app.nodes.agent import FakeAgent, tool_call_turn
from app.nodes.run_tools import FakeRunTools
from app.tools.find_tickets.fake import FakeFindTickets, default_tickets
from app.tools.find_tickets.models import FindTicketsResult

# Zapytanie, które atrapa agenta wysyła do `find_tickets` — w kształcie korpusu, zmyślone.
FAKE_SEARCH_ARGUMENTS = {
    "problem":  "Nie przychodzą przesyłki z e-Doręczeń",
    "symptoms": "Brak nowych przesyłek w skrzynce, nadawcy potwierdzają wysyłkę",
}


def fake_search_nodes(
    respond_tool_name: str,        # np. "respond_search"
    output:            BaseModel,  # np. Proposal(text="1. Od kiedy…")
) -> tuple[FakeAgent, FakeRunTools]:
    """
    Description:
    Atrapy agenta i narzędzi dla grafu z narzędziami wiedzy: agent najpierw szuka `find_tickets`,
    potem wywołuje narzędzie odpowiedzi z `output` w argumentach; `run_tools` odpowiada wbudowanym
    zestawem `FakeFindTickets` (jeden objaw, trzy przyczyny) — tekstem i źródłami z tych samych
    `render_for_model()` i `cite()`, co atrapa narzędzia.

    Example args:
        respond_tool_name="respond_suggest_questions"
        output=Proposal(text="1. Od kiedy…")

    Example result:
        (FakeAgent z dwiema turami, FakeRunTools z trzema źródłami find_tickets)
    """
    finder = FakeFindTickets()
    result = FindTicketsResult(items=default_tickets())

    agent = FakeAgent([
        tool_call_turn("find_tickets", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn(respond_tool_name, output.model_dump(), call_id="call_2"),
    ])

    run_tools = FakeRunTools(
        result_text = finder.render_for_model(result),
        sources     = finder.cite(result),
    )

    return agent, run_tools
