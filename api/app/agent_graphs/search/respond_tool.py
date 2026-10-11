from pathlib import Path

from app.agent_graphs.search.models import SearchNotes
from app.core_util.json_schema import json_schema_without_docs
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_search"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model kończy wyszukiwanie i oddaje uwagi dla wdrożeniowca
    (`SearchNotes`). Źródła i zapytania biorą się z przebiegu, nie z argumentów.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_search", description="Kończy wyszukiwanie…",
                       parameters={"type": "object", "properties": {"internal_notes": {…}}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_docs(SearchNotes),
    )

    return tool
