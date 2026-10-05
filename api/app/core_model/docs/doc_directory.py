from pathlib import Path

from pydantic import BaseModel, Field

from app.core_model.docs.doc_manifest import DocManifest


class DocDirectory(BaseModel):
    """
    Description:
    Katalog jednego dokumentu po wczytaniu z dysku: manifest, treść sekcji i wszystko, co się
    w nim nie zgadza.

    Do czego:
    Niesie i treść, i werdykt, bo czyta się je raz: `helpdesk docs validate` wypisuje z tego
    błędy i ostrzeżenia, a `helpdesk docs index` bierze manifest i treść. Błąd wstrzymuje
    indeksację, ostrzeżenie tylko trafia do raportu.
    """

    path:     Path               = Field(examples=[Path("data/unsafe/instruction/administrator")])
    # Brak, gdy manifestu nie ma albo nie dało się go przeczytać — powód stoi wtedy w `errors`.
    manifest: DocManifest | None = Field(default=None)
    # Treść plików `.md` po identyfikatorze sekcji — dosłownie, tak jak leży na dysku.
    bodies:   dict[str, str]     = Field(default_factory=dict)
    errors:   list[str]          = Field(default_factory=list, examples=[["brak pliku a.md"]])
    warnings: list[str]          = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """
        Description:
        Mówi, czy katalog da się zaindeksować: jest manifest i nic się z nim nie kłóci.

        Example args:
            (brak)

        Example result:
            True
        """
        return not self.errors
