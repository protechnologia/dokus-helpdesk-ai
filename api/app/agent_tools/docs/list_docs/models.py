from pydantic import BaseModel, ConfigDict, Field

from app.core_model.docs.doc_section import DocSection


class ListDocsArgs(BaseModel):
    """
    Description:
    Argumenty `list_docs` — nie ma żadnych. Narzędzie zwraca cały spis treści; zawężenie do
    jednego dokumentu dojdzie, gdy spis właściwej dokumentacji okaże się na to za długi (p. 15).
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")


class ListDocsResult(BaseModel):
    """
    Description:
    Spis treści dokumentacji: wszystkie sekcje w kolejności, w jakiej stoją w dokumentach.
    """

    model_config = ConfigDict(extra="forbid")

    sections: list[DocSection] = Field(default_factory=list)
