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
    """Sprawdza, czy ze schematu JSON modelu znika cała dokumentacja, także z modelu zagnieżdżonego:
    docstringi klas, opisy pól i przykłady.

    Wyłapuje dokumentację, która przecieka do schematu: schemat idzie do modelu językowego jako
    definicja narzędzia, więc model dostałby notatki pisane dla programisty i przykłady, które
    przepisuje dosłownie."""
    text = json.dumps(SCHEMA, ensure_ascii=False)

    assert "programisty" not in text
    assert "opis pola"   not in text
    assert "examples"    not in text


def test_fields_named_like_keywords_survive() -> None:
    """Sprawdza, czy pola modelu nazwane `title` i `description` zostają w schemacie obok pola
    `inner`, choć tak samo nazywają się usuwane słowa kluczowe dokumentacji.

    Wyłapuje wycinanie po samej nazwie klucza: pole danych o nazwie `title` zniknęłoby ze schematu,
    a model językowy nie wiedziałby, że ma je wypełnić."""
    assert set(SCHEMA["properties"]) == {"title", "description", "inner"}


def test_the_shape_stays() -> None:
    """Sprawdza, czy kształt schematu zostaje bez zmian: lista pól wymaganych (`title` i `inner`),
    typ pola `title` oraz definicja zagnieżdżonego modelu, w której z pola `code` zostaje sam typ.

    Wyłapuje wycinanie, które razem z dokumentacją usuwa typy, pola wymagane albo zagnieżdżone
    definicje: model językowy dostałby schemat, według którego nie da się zbudować poprawnej
    odpowiedzi."""
    assert SCHEMA["required"]                     == ["title", "inner"]
    assert SCHEMA["properties"]["title"]["type"]  == "string"
    assert SCHEMA["$defs"]["Inner"]["properties"] == {"code": {"type": "string"}}
