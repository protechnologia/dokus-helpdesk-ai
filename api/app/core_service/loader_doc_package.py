"""
Description:
Czyta paczkę dokumentacji z dysku i mówi, co się w niej nie zgadza. Paczka to katalog,
w którym każdy dokument ma swój podkatalog: `manifest.json` i plik `<section_id>.md` z treścią
na każdą sekcję. Nie woła żadnej usługi — z jej wyniku korzysta i `helpdesk docs validate`,
i `helpdesk docs index`.

Przed — paczka na dysku:

    data/unsafe/instruction/
    ├── instrukcja-administratora/
    │   ├── manifest.json                    dokument, wydanie, sekcje w kolejności dokumentu
    │   ├── adm-kancelaria-edoreczenia.md    treść sekcji, dosłownie
    │   └── adm-kancelaria-epuap.md
    └── instrukcja-uzytkownika/
        ├── manifest.json
        └── usr-wysylka-status-w-toku.md

Po — `DocPackage`:

    DocPackage(
        path        = Path("data/unsafe/instruction"),
        directories = [
            DocDirectory(path=…/instrukcja-administratora, manifest=DocManifest(…),
                         bodies={"adm-kancelaria-edoreczenia": "Uprawnienie nadaje…", …}),
            DocDirectory(path=…/instrukcja-uzytkownika, manifest=DocManifest(…), bodies={…}),
        ],
        errors      = [],
    )

Co jest sprawdzane:

| co                                           | wynik                               |
|----------------------------------------------|-------------------------------------|
| brak `manifest.json` albo manifest z błędami | błąd katalogu                       |
| sekcja z manifestu bez pliku `.md`           | błąd katalogu                       |
| plik `.md` bez wpisu w manifeście            | błąd katalogu                       |
| plik sekcji pusty albo nie w UTF-8           | błąd katalogu                       |
| ten sam `section_id` w kilku dokumentach     | błąd paczki                         |
| sekcja dłuższa niż `SECTION_WARN_CHARS`      | ostrzeżenie, niczego nie wstrzymuje |

O czym pamiętać przy zmianach:

- Każda wada trafia do wyniku, zamiast przerywać czytanie: przebieg robi się po to, żeby
  zobaczyć wszystkie problemy paczki naraz.
- Treść sekcji wraca dosłownie, bez przycinania — w tej postaci idzie do bazy i do agenta.
- Zgodność manifestu z katalogiem działa w obie strony. Plik `.md` bez wpisu to sekcja, o której
  nikt by się nie dowiedział: nie trafiłaby do indeksu i nic by tego nie zgłosiło.
"""

from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from app.core_model.docs.doc_directory import DocDirectory
from app.core_model.docs.doc_manifest import DocManifest
from app.core_model.docs.doc_package import DocPackage
from app.core_util.validation_text import describe_validation_error

MANIFEST_NAME  = "manifest.json"
SECTION_SUFFIX = ".md"

# Powyżej tej długości sekcja dostaje ostrzeżenie: agent czyta sekcje w całości, do kilku naraz.
# Wartość tymczasowa — tyle znaków to około 8192 tokenów; właściwy próg ustali przygotowanie
# prawdziwej dokumentacji (CLAUDE.md -> p. 55).
SECTION_WARN_CHARS = 18_000


def load_doc_package(
    root: Path,  # np. Path("data/unsafe/instruction")
) -> DocPackage:
    """
    Description:
    Czyta paczkę dokumentacji: każdy podkatalog jako jeden dokument, w kolejności nazw, żeby dwa
    przebiegi po tej samej paczce dawały porównywalne raporty.

    Pusty katalog daje pustą, poprawną paczkę — katalog właściwej dokumentacji jest pusty, dopóki
    jej nie przygotowano.

    Example args:
        root=Path("data/unsafe/instruction")

    Example result:
        DocPackage(path=Path("data/unsafe/instruction"), directories=[DocDirectory(…), …])

    Raises:
        NotADirectoryError: ścieżka nie istnieje albo nie jest katalogiem
    """
    if not root.is_dir():
        raise NotADirectoryError(f"nie jest katalogiem: {root}")

    # --- wskazano katalog jednego dokumentu zamiast paczki ---
    if (root / MANIFEST_NAME).is_file():
        error = (
            f"{root} to katalog jednego dokumentu (ma {MANIFEST_NAME}) — podaj katalog nadrzędny, "
            f"w którym każdy dokument ma swój podkatalog"
        )

        return DocPackage(path=root, errors=[error])

    # Katalogi ukryte (`.git`, `.ipynb_checkpoints`) nie są dokumentami.
    paths = sorted(
        path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    directories = [_load_directory(path) for path in paths]

    package = DocPackage(
        path        = root,
        directories = directories,
        errors      = _shared_section_ids(directories),
    )

    return package


def _load_directory(
    path: Path,  # np. Path("data/unsafe/instruction/instrukcja-administratora")
) -> DocDirectory:
    """
    Description:
    Czyta katalog jednego dokumentu: manifest, a potem plik każdej sekcji. Bez manifestu nie ma
    czego sprawdzać dalej, więc katalog wraca z samym błędem.

    Example args:
        path=Path("data/unsafe/instruction/instrukcja-administratora")

    Example result:
        DocDirectory(path=…, manifest=DocManifest(…), bodies={"adm-kancelaria-epuap": "…"})
    """
    manifest, errors = _read_manifest(path / MANIFEST_NAME)

    if manifest is None:
        return DocDirectory(path=path, errors=errors)

    bodies:   dict[str, str] = {}
    warnings: list[str]      = []

    # --- manifest → katalog: każda sekcja ma swój plik ---
    for section in manifest.sections:
        body, error = _read_section(path / f"{section.section_id}{SECTION_SUFFIX}")

        if body is None:
            errors.append(error)
            continue

        bodies[section.section_id] = body

        if len(body) > SECTION_WARN_CHARS:
            warnings.append(
                f"sekcja {section.section_id} ma {len(body)} znaków (próg {SECTION_WARN_CHARS}) "
                f"— agent czyta sekcje w całości; rozważ podział na krótsze"
            )

    # --- katalog → manifest: każdy plik `.md` ma swój wpis ---
    listed = {section.section_id for section in manifest.sections}

    for file in sorted(path.glob(f"*{SECTION_SUFFIX}")):
        if file.stem not in listed:
            errors.append(f"plik bez wpisu w manifeście: {file.name}")

    directory = DocDirectory(
        path     = path,
        manifest = manifest,
        bodies   = bodies,
        errors   = errors,
        warnings = warnings,
    )

    return directory


def _read_manifest(
    path: Path,  # np. Path("data/unsafe/instruction/instrukcja-administratora/manifest.json")
) -> tuple[DocManifest | None, list[str]]:
    """
    Description:
    Czyta `manifest.json` do `DocManifest`. Oddaje manifest albo — zamiast niego — listę
    powodów, dla których nie dało się go przeczytać.

    Example args:
        path=Path("data/unsafe/instruction/instrukcja-administratora/manifest.json")

    Example result:
        (DocManifest(document="Instrukcja administratora", version="4.12", …), [])
    """
    # --- katalog bez manifestu ---
    if not path.is_file():
        return None, [f"brak pliku {MANIFEST_NAME}"]

    try:
        manifest = DocManifest.model_validate_json(path.read_text(encoding="utf-8"))
    # Wadliwy JSON też trafia tutaj: pydantic zgłasza go jako ValidationError typu `json_invalid`.
    except ValidationError as exc:
        errors = [f"{MANIFEST_NAME}: {line}" for line in describe_validation_error(exc)]

        return None, errors
    # Rzucany przez read_text(), zanim pydantic zobaczy treść.
    except UnicodeDecodeError as exc:
        return None, [f"{MANIFEST_NAME} nie jest tekstem UTF-8: {exc}"]

    return manifest, []


def _read_section(
    path: Path,  # np. Path("…/instrukcja-administratora/adm-kancelaria-edoreczenia.md")
) -> tuple[str | None, str]:
    """
    Description:
    Czyta treść jednej sekcji. Oddaje treść dosłownie albo — zamiast niej — powód, dla którego
    pliku nie da się użyć.

    Example args:
        path=Path("…/instrukcja-administratora/adm-kancelaria-edoreczenia.md")

    Example result:
        ("Uprawnienie do kancelarii e-Doręczeń nadaje administrator…", "")
    """
    # --- sekcja z manifestu bez pliku ---
    if not path.is_file():
        return None, f"brak pliku {path.name}"

    try:
        body = path.read_text(encoding="utf-8")
    # Plik w innym kodowaniu: błąd tej sekcji, a nie wyjątek przerywający czytanie paczki.
    except UnicodeDecodeError as exc:
        return None, f"{path.name} nie jest tekstem UTF-8: {exc}"

    # --- plik jest, ale bez treści: sekcja bez tekstu niczego nie opisuje ---
    if not body.strip():
        return None, f"{path.name} jest pusty"

    return body, ""


def _shared_section_ids(
    directories: list[DocDirectory],  # np. [DocDirectory(path=…/administrator, …), …]
) -> list[str]:
    """
    Description:
    Znajduje identyfikatory sekcji użyte w więcej niż jednym dokumencie. Identyfikator jest
    kluczem w tabeli i w wynikach narzędzi, więc druga sekcja nadpisałaby pierwszą bez śladu.

    Example args:
        directories=[DocDirectory(path=Path("…/administrator"), manifest=DocManifest(…)), …]

    Example result:
        ["section_id wstep jest w kilku dokumentach: administrator, uzytkownik"]
    """
    owners: dict[str, list[str]] = defaultdict(list)

    for directory in directories:
        # Katalog bez czytelnego manifestu ma już swój błąd.
        if directory.manifest is None:
            continue

        for section in directory.manifest.sections:
            owners[section.section_id].append(directory.path.name)

    errors = [
        f"section_id {section_id} jest w kilku dokumentach: {', '.join(names)}"
        for section_id, names in sorted(owners.items())
        if len(names) > 1
    ]

    return errors
