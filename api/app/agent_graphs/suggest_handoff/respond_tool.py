from pathlib import Path

from app.core_model.suggest_proposal import Proposal
from app.core_util.json_schema import json_schema_without_docs
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_suggest_handoff"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model oddaje tekst przekazania sprawy — kontrakt wyjścia grafu.
    Nic go nie wykonuje: węzeł `respond` waliduje argumenty do `Proposal`.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_suggest_handoff", description="Oddaje tekst przekazania…",
                       parameters={"type": "object", "properties": {"text": …}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_docs(Proposal),
    )

    return tool
