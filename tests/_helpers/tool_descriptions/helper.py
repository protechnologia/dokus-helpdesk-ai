"""
Description:
Tabelka argumentów z opisu narzędzia i typy argumentów ze schematu, w jednym zapisie, żeby test
mógł porównać jedno z drugim.

Typ w tabelce to nazwa typu z JSON-a, bo model wypełnia argumenty JSON-em i obok opisu dostaje
schemat w JSON Schema:

| schemat pola                                     | typ w tabelce      |
|--------------------------------------------------|--------------------|
| `{"type": "string"}`, także z `enum`             | `string`           |
| `{"type": "integer"}`                            | `integer`          |
| `{"type": "array", "items": {"type": "string"}}` | `string[]`         |
| `null` w `anyOf` pola wymaganego                 | `string albo null` |
| `null` w `anyOf` pola opcjonalnego               | `string`           |

Pole opcjonalne przyjmuje `null` tylko jako „nie podano”, a opis nazywa je opcjonalnym, więc typ
w tabelce go nie wymienia. Pole wymagane z `null` (lista pytań w `suggest_questions`) przyjmuje
go jako odpowiedź i typ mówi o tym wprost.
"""

from tests._helpers.tool_descriptions.constants import NULLABLE_SUFFIX


def argument_types(
    description: str,  # np. "# Jak wywoływać\n\n| argument | typ | …\n|---…\n| path | string | …"
) -> dict[str, str]:
    """
    Description:
    Odczytuje z sekcji „Jak wywoływać" opisu narzędzia tabelkę argumentów: nazwę argumentu i typ.
    Opis bez tabelki (narzędzie bez argumentów) daje pusty słownik.

    Example args:
        description="# Jak wywoływać\n\n| argument | typ | przykłady | opis |\n|---|---|---|---|\n
                     | path | string | \"src\" | Ścieżka… |\n\n# Co zwraca…"

    Example result:
        {"path": "string"}
    """
    section = description.split("# Jak wywoływać")[1].split("# Co zwraca")[0]
    rows    = [line for line in section.splitlines() if line.startswith("|")]

    # --- pierwszy wiersz to nagłówek, drugi to kreski pod nim ---
    cells = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]
    types = {row[0]: row[1] for row in cells}

    return types


def schema_types(
    schema: dict,  # np. {"properties": {"path": {"type": "string"}}, "required": ["path"]}
) -> dict[str, str]:
    """
    Description:
    Typy argumentów ze schematu narzędzia, zapisane tak, jak ma je podawać tabelka w opisie.

    Example args:
        schema={"properties": {"text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                               "path": {"anyOf": [{"type": "string"}, {"type": "null"}],
                                        "default": None}},
                "required": ["text"]}

    Example result:
        {"text": "string albo null", "path": "string"}
    """
    required = set(schema.get("required", []))
    types    = {}

    for name, field in schema.get("properties", {}).items():
        variants = field.get("anyOf", [field])
        named    = [_type_name(variant) for variant in variants if variant.get("type") != "null"]
        nullable = len(named) < len(variants)

        # --- `null` jako odpowiedź tylko w polu wymaganym; w opcjonalnym to brak argumentu ---
        suffix      = NULLABLE_SUFFIX if nullable and name in required else ""
        types[name] = f"{named[0]}{suffix}"

    return types


def _type_name(
    variant: dict,  # np. {"type": "array", "items": {"type": "string"}}
) -> str:
    """
    Description:
    Nazwa typu jednego wariantu pola: tablica dostaje nawiasy po typie swoich elementów.

    Example args:
        variant={"type": "array", "items": {"minLength": 1, "type": "string"}}

    Example result:
        "string[]"
    """
    if variant["type"] == "array":
        return f"{variant['items']['type']}[]"

    return variant["type"]
