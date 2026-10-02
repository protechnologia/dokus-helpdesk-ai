from typing import Any

from pydantic import BaseModel

# Słowa kluczowe schematu, które niosą dokumentację, a nie kształt danych.
DOC_KEYWORDS = frozenset({"title", "description", "examples"})

# Słowa kluczowe, pod którymi leży mapa „nazwa → schemat": ich klucze to nazwy pól, nie słowa
# kluczowe, więc pole nazwane `title` musi przetrwać.
NAMED_SCHEMAS = frozenset({"properties", "$defs", "patternProperties"})


def json_schema_without_docs(
    model: type[BaseModel],  # np. Verdict
) -> dict[str, Any]:
    """
    Description:
    Schemat JSON modelu Pydantic bez dokumentacji: bez `title`, `description` i `examples` na
    każdym poziomie. Zostaje sam kształt — typy, pola wymagane, `enum`, wartości domyślne.

    Pydantic wstawia do schematu docstring klasy i przykłady z `Field(examples=…)`. Oba pisane są
    dla programisty, a schemat idzie do modelu językowego jako definicja narzędzia — opis dla
    modelu ma własny dokument, a gotowe przykłady model przepisuje dosłownie.

    Example args:
        model=Verdict

    Example result:
        {"type": "object", "additionalProperties": False, "required": ["verdict"],
         "properties": {"verdict": {"enum": ["pass", "block"], "type": "string"}, …}}
    """
    schema = _strip_docs(model.model_json_schema())

    return schema


def _strip_docs(
    node: Any,  # np. {"title": "Verdict", "type": "object", "properties": {…}}
) -> Any:
    """
    Description:
    Rekurencyjnie usuwa słowa kluczowe dokumentacji; w mapach nazwanych schematów zachowuje klucze,
    bo to nazwy pól.

    Example args:
        node={"title": "Hint", "type": "string", "examples": ["Dopisz…"]}

    Example result:
        {"type": "string"}
    """
    # --- lista: np. `anyOf`, `items` w postaci krotki ---
    if isinstance(node, list):
        return [_strip_docs(item) for item in node]

    # --- wartość prosta: typ, wartość domyślna, element `enum` ---
    if not isinstance(node, dict):
        return node

    stripped: dict[str, Any] = {}

    for key, value in node.items():
        # dokumentacja — wypada
        if key in DOC_KEYWORDS:
            continue

        # mapa nazwa → schemat — klucze zostają, schematy pod nimi czyścimy
        if key in NAMED_SCHEMAS:
            stripped[key] = {name: _strip_docs(schema) for name, schema in value.items()}
            continue

        stripped[key] = _strip_docs(value)

    return stripped
