import json

from pydantic import BaseModel, Field

from app.core_util.json_schema import json_schema_without_docs


class Inner(BaseModel):
    """Notatka dla programisty w zagnieżdżonym modelu."""

    code: str = Field(description="opis pola", examples=["E-1"])


class Outer(BaseModel):
    """Notatka dla programisty — nie ma prawa dotrzeć do modelu."""

    # Pola nazwane jak słowa kluczowe dokumentacji: muszą przetrwać, bo to nazwy pól.
    title:       str   = Field(examples=["Brak przesyłek"])
    description: str   = Field(default="", description="opis pola")
    inner:       Inner


SCHEMA = json_schema_without_docs(Outer)


def test_documentation_is_gone_at_every_level() -> None:
    """Docstringi, opisy pól i przykłady — także w zagnieżdżonym modelu → wycięte w całości."""
    text = json.dumps(SCHEMA, ensure_ascii=False)

    assert "programisty" not in text
    assert "opis pola"   not in text
    assert "examples"    not in text


def test_fields_named_like_keywords_survive() -> None:
    """Pola `title` i `description` → zostają w `properties`: wycinamy słowa kluczowe, nie pola."""
    assert set(SCHEMA["properties"]) == {"title", "description", "inner"}


def test_the_shape_stays() -> None:
    """Pola wymagane, typy i odwołania do zagnieżdżonych modeli → bez zmian."""
    assert SCHEMA["required"]                     == ["title", "inner"]
    assert SCHEMA["properties"]["title"]["type"]  == "string"
    assert SCHEMA["$defs"]["Inner"]["properties"] == {"code": {"type": "string"}}
