from pathlib import Path

from app.graph.polish.models import PolishedText
from app.llm import ToolDefinition
from app.util.json_schema import json_schema_without_docs
from app.util.markdown import read_document

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_polish"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model oddaje poprawiony tekst — kontrakt wyjścia grafu. Nic go nie
    wykonuje: węzeł `respond` waliduje argumenty do `PolishedText`.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_polish", description="Oddaje poprawiony tekst…",
                       parameters={"type": "object", "properties": {"text": …}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_docs(PolishedText),
    )

    return tool
