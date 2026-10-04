from pathlib import Path

from app.agent_graphs.search.models import SearchDone
from app.engine_llm import ToolDefinition
from app.util.json_schema import json_schema_without_docs
from app.util.markdown import read_document

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_search"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model kończy wyszukiwanie — bez argumentów (`SearchDone`). Wynik
    to źródła i zapytania z przebiegu, nie treść od modelu.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_search", description="Kończy wyszukiwanie…",
                       parameters={"type": "object", "properties": {}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_docs(SearchDone),
    )

    return tool
