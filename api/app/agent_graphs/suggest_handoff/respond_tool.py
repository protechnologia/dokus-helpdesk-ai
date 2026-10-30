from pathlib import Path

from app.core_model.graphs.proposal import Proposal
from app.core_util.json_schema import json_schema_without_docs, json_schema_without_fields
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_suggest_handoff"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"

# Pola propozycji, o które model nie jest pytany. Uwag tu nie ma: model ma tylko wątek, który
# wdrożeniowiec i tak widzi, więc nie miałby czego dopisać.
FILLED_BY_GRAPH = ("internal_notes",)


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model oddaje tekst przekazania sprawy — kontrakt wyjścia grafu.
    Schemat to `Proposal` bez dokumentacji i bez pól `FILLED_BY_GRAPH`; nic go nie wykonuje:
    węzeł `respond` dokłada te pola i waliduje całość do `Proposal`.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_suggest_handoff", description="Oddaje tekst przekazania…",
                       parameters={"type": "object", "properties": {"text": …}, …})
    """
    schema = json_schema_without_docs(Proposal)

    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_fields(schema, FILLED_BY_GRAPH),
    )

    return tool
