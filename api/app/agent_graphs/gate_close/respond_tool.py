from pathlib import Path

from app.engine_llm import ToolDefinition
from app.model.gate_verdict import Verdict
from app.util.json_schema import json_schema_without_docs
from app.util.markdown import read_document

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_gate_close"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model wydaje werdykt bramki — kontrakt wyjścia grafu. Nic go nie
    wykonuje: wywołanie kończy pętlę, a węzeł `respond` waliduje jego argumenty do `Verdict`.

    Schemat argumentów to `Verdict` bez dokumentacji: znaczenie pól opisuje `respond_tool.md`,
    a pola `sources` nie ma z założenia — źródła powstają z `cite()`, nigdy z deklaracji modelu.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_gate_close", description="Wydaje werdykt bramki…",
                       parameters={"type": "object", "properties": {"verdict": …}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_docs(Verdict),
    )

    return tool
