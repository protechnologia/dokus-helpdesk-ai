from pathlib import Path

from app.core_model.gate_verdict import Verdict
from app.core_util.json_schema import json_schema_without_docs
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_gate_reply"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model wydaje werdykt bramki wysyłki — kontrakt wyjścia grafu. Nic
    go nie wykonuje: wywołanie kończy turę, a węzeł `respond` waliduje argumenty do `Verdict`.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_gate_reply", description="Wydaje werdykt bramki wysyłki…",
                       parameters={"type": "object", "properties": {"verdict": …}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_docs(Verdict),
    )

    return tool
