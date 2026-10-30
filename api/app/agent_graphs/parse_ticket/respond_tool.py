from pathlib import Path

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_util.json_schema import json_schema_without_docs, json_schema_without_fields
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

# Konwencja `respond_<graf>`: wywołanie tego narzędzia prowadzi do węzła `respond`.
RESPOND_TOOL_NAME = "respond_parse_ticket"
DESCRIPTION_FILE  = Path(__file__).parent / "respond_tool.md"

# Pola karty, o które model nie jest pytany: tożsamość i datę daje źródło, wersję słownika — graf,
# który go wstawił do promptu. Model, który by je wymyślił, nie ma jak ich podać.
FILLED_BY_GRAPH = ("ticket_id", "date", "resolution_vocabulary_version")

# Nagłówek sekcji z regułami pól w respond_tool.md — granica dla `field_rules()`.
RULES_HEADING = "# Zasady"


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
    schema = json_schema_without_docs(ParsedTicket)

    tool = ToolDefinition(
        name        = RESPOND_TOOL_NAME,
        description = read_document(DESCRIPTION_FILE).rstrip(),
        parameters  = json_schema_without_fields(schema, FILLED_BY_GRAPH),
    )

    return tool


def field_rules() -> str:
    """
    Description:
    Zwraca sekcję „Zasady" z opisu narzędzia, w której stoją reguły pól („Wypełniając pole
    `pole`, …"). Wystawiony dla testu-strażnika: nazwa pola pada też w tabelce argumentów, więc
    szukanie w całym opisie przeszłoby po skasowaniu reguły pola.

    Example args:
        (brak)

    Example result:
        "\\n\\n- Wywołaj raz, po przeczytaniu całego wątku…\\n- Wypełniając pole `component`, …"
    """
    # Cięcie na NASTĘPNYM nagłówku sekcji, jakimkolwiek: sekcja dopisana za „Zasadami” nie może
    # po cichu poszerzyć bloku o tekst, w którym pada nazwa każdego pola.
    body = respond_tool().description.split(f"\n{RULES_HEADING}\n", 1)[1]

    return body.split("\n# ", 1)[0]
