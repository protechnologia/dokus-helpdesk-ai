from pathlib import Path

from pydantic import BaseModel, Field

from app.core_model.doc_directory import DocDirectory


class DocPackage(BaseModel):
    """
    Description:
    Paczka dokumentacji po wczytaniu z dysku: katalog na dokument i błędy, które dotyczą
    paczki jako całości.

    Flow:
        1. `load_doc_package()` czyta każdy podkatalog do `DocDirectory`, w kolejności nazw.
        2. Ponad katalogami sprawdza to, czego jeden katalog nie widzi — np. ten sam
           `section_id` w dwóch dokumentach — i zapisuje w `errors`.
        3. Wołający (CLI, import) wypisuje wynik i decyduje, co dalej; paczka niczego nie
           wypisuje i niczego nie przerywa.
    """

    path:        Path               = Field(examples=[Path("data/unsafe/instruction")])
    directories: list[DocDirectory] = Field(default_factory=list)
    errors:      list[str]          = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """
        Description:
        Mówi, czy całą paczkę da się zaimportować: bez błędów ponad katalogami i w każdym
        katalogu. Pusta paczka jest poprawna — katalog właściwej dokumentacji bywa pusty.

        Example args:
            (brak)

        Example result:
            False
        """
        return not self.errors and all(directory.ok for directory in self.directories)

    @property
    def section_count(self) -> int:
        """
        Description:
        Liczy sekcje ze wszystkich manifestów, które dało się przeczytać.

        Example args:
            (brak)

        Example result:
            27
        """
        count = sum(
            len(directory.manifest.sections)
            for directory in self.directories
            if directory.manifest is not None
        )

        return count

    @property
    def warnings(self) -> list[str]:
        """
        Description:
        Zbiera ostrzeżenia ze wszystkich katalogów, w kolejności katalogów.

        Example args:
            (brak)

        Example result:
            ["sekcja adm-wykaz-uprawnien ma 20439 znaków (próg 18000)…"]
        """
        return [warning for directory in self.directories for warning in directory.warnings]
