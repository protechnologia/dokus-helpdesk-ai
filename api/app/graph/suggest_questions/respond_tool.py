from pathlib import Path

from app.llm import ToolDefinition
from app.model.suggest_proposal import Proposal
from app.util.json_schema import json_schema_without_docs
from app.util.markdown import read_document

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_suggest_questions"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model oddaje listę pytań — kontrakt wyjścia grafu. Nic go nie
    wykonuje: węzeł `respond` waliduje argumenty do `Proposal`. Źródeł w schemacie nie ma —
    powstają z `cite()`.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_suggest_questions", description="Oddaje …",
                       parameters={"type": "object", "properties": {"text": …}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_docs(Proposal),
    )

    return tool
