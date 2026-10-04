from pathlib import Path
from typing import Any

from app.engine_llm import ToolDefinition
from app.model.ticket_parsed import ParsedTicket
from app.util.json_schema import json_schema_without_docs
from app.util.markdown import read_document

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_parse_ticket"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"

# Pola karty, o które model nie jest pytany: tożsamość i datę daje źródło, wersję słownika — graf,
# który go wstawił do promptu. Model, który by je wymyślił, nie ma jak ich podać.
FILLED_BY_GRAPH = ("ticket_id", "date", "resolution_vocabulary_version")

# Nagłówek sekcji z opisami pól w respond_tool.md — granica dla `field_rules()`.
FIELDS_HEADING = "## Pola karty"


def respond_tool() -> ToolDefinition:
    """
    Description:
    Definicja narzędzia, którym model oddaje kartę zgłoszenia — kontrakt wyjścia grafu i część
    kontraktu artefaktu (zasada 7). Schemat to `ParsedTicket` bez dokumentacji i bez pól
    `FILLED_BY_GRAPH`; węzeł `respond` dokłada je ze stanu i waliduje całość do `ParsedTicket`.

    Example args:
        (brak)

    Example result:
        ToolDefinition(name="respond_parse_ticket", description="Oddaje kartę zgłoszenia…",
                       parameters={"type": "object", "properties": {"component": …}, …})
    """
    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = _without_fields(json_schema_without_docs(ParsedTicket), FILLED_BY_GRAPH),
    )

    return tool


def field_rules() -> str:
    """
    Description:
    Zwraca sam blok opisów pól z opisu narzędzia. Wystawiony dla testu-strażnika: nazwa pola pada
    też w przykładach, więc szukanie w całym opisie przeszłoby po skasowaniu opisu pola.

    Example args:
        (brak)

    Example result:
        "\\n\\n`component` — czego sprawa dotyczy. Jedna wartość…"
    """
    # Cięcie na NASTĘPNYM nagłówku drugiego poziomu, jakimkolwiek: sekcja wstawiona za polami nie
    # może po cichu poszerzyć bloku o przykłady JSON, w których pada nazwa każdego pola.
    body = respond_tool().description.split(FIELDS_HEADING, 1)[1]

    return body.split("\n## ", 1)[0]


def _without_fields(
    schema: dict[str, Any],  # np. {"type": "object", "properties": {"ticket_id": …}, …}
    fields: tuple[str, ...], # np. ("ticket_id", "date")
) -> dict[str, Any]:
    """
    Description:
    Usuwa ze schematu obiektu podane pola — z `properties` i z `required`.

    Example args:
        schema={"properties": {"ticket_id": {…}, "problem": {…}}, "required": ["ticket_id"]}
        fields=("ticket_id",)

    Example result:
        {"properties": {"problem": {…}}, "required": []}
    """
    trimmed = {
        **schema,
        "properties": {
            name: value for name, value in schema["properties"].items() if name not in fields
        },
        "required": [name for name in schema.get("required", []) if name not in fields],
    }

    return trimmed
