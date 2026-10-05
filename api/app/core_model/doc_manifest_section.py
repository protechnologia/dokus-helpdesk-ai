from pydantic import BaseModel, ConfigDict, Field

# Identyfikator sekcji jest też nazwą jej pliku (`<section_id>.md`), więc nie może wyjść poza
# katalog dokumentu: litery, cyfry, kropka, podkreślenie i łącznik, od litery albo cyfry.
SECTION_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class DocManifestSection(BaseModel):
    """
    Description:
    Wpis jednej sekcji w `manifest.json` dokumentu: identyfikator, miejsce w dokumencie, tytuł
    i opis. Dokumentu ani wydania tu nie ma — stoją raz, w nagłówku manifestu (`DocManifest`).
    """

    model_config = ConfigDict(extra="forbid")

    section_id:   str       = Field(pattern=SECTION_ID_PATTERN, examples=["adm-kancelaria-epuap"])
    chapter_path: list[str] = Field(default_factory=list, examples=[["Uprawnienia", "Kancelaria"]])
    title:        str       = Field(min_length=1, examples=["Uprawnienie do skrzynki ePUAP"])
    description:  str       = Field(min_length=1, examples=["Kto nadaje uprawnienie i gdzie"])
