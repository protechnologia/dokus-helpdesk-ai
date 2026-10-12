"""
Description:
Czyta z paczki kodu aplikacji to, co stoi OBOK kodu i o nim mówi: opis projektu i metryczkę.
Kodu z `repo/` nie dotyka — to robi `loader_code_package.py` — i nie przyjmuje żadnej ścieżki
od modelu: oba pliki leżą w stałych miejscach.

| plik w katalogu paczki | kto go pisze                      | co z niego bierzemy      |
|------------------------|-----------------------------------|--------------------------|
| `project.md`           | człowiek, ręcznie                 | opis projektu, w całości |
| `manifest.json`        | skrypt paczki, przy każdej budowie | gałąź i dzień budowy     |

Przed — dwa pliki paczki z aplikacji syntetycznej:

    project.md     "<!-- notatka dla nas -->\\nZmyślona aplikacja urzędu na Symfony 1: backend…"
    manifest.json  {"source": "data/safe/code/source", "branch": null, "built_on": "2026-10-11", …}

Po:

    description.read_text()          →  "Zmyślona aplikacja urzędu na Symfony 1: backend…"
    description.read_package_info()  →  CodePackageInfo(branch=None, built_on=date(2026, 10, 11))

Co jest sprawdzane:

| co                                                    | wynik                    |
|-------------------------------------------------------|--------------------------|
| opisu projektu nie ma, jest pusty albo nie w UTF-8    | `CodePackageConfigError` |
| metryczki nie ma albo nie niesie gałęzi i dnia budowy | `CodePackageConfigError` |

O czym pamiętać przy zmianach:

- Oba pliki leżą OBOK `repo/`, nie w nim: skrypt paczki kasuje `repo/` przy każdej budowie,
  a plik w `repo/` wychodziłby w szukaniu i w spisie katalogu jak kod.
- Oba czyta się z dysku przy każdym wywołaniu, bez pamiętania: opis poprawia się bez restartu
  usługi, a metryczkę podmienia przebudowa paczki.
- Brak opisu albo metryczki to błąd wdrożenia, jak brak paczki: do modelu nie wraca. Model,
  który dostałby „paczka nie ma opisu", szukałby dalej bez niego i nikt by braku nie zauważył.
- Komentarze redakcyjne w opisie (`<!-- … -->`) są wycinane, jak w promptach: notatka dla nas
  nie dociera do modelu.
- Opis nie nazywa się `description.md`, bo tak nazywa się opis każdego narzędzia agenta dla
  modelu.
- Czy ścieżki z opisu istnieją w paczce, sprawdza skrypt paczki
  (`scripts/build_code_package.py check-description`), nie ten plik.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.core_model.code.code_package_info import CodePackageInfo
from app.core_service.loader_code_package import CodePackageConfigError
from app.core_util.markdown import read_document

# Opis projektu: pisze go człowiek, skrypt paczki go nie rusza.
DESCRIPTION_FILE = "project.md"

# Metryczka paczki: zapisuje ją skrypt paczki przy każdej budowie.
MANIFEST_FILE = "manifest.json"


class CodeDescription:
    """
    Description:
    To, co paczka kodu aplikacji mówi o sobie obok samego kodu: opis projektu i metryczka.

    Do czego:
    Na niej stoi narzędzie agenta `describe_code`, a `quote_code` bierze z niej gałąź do tytułu
    źródła. Osobno od `CodePackage`, bo robi coś innego: tamta pilnuje, żeby ścieżka od modelu
    nie wyszła poza `repo/`, a tu nie ma ani ścieżki od modelu, ani kodu. Tylko do odczytu.

    Flow:
        1. Konstruktor zapamiętuje katalog paczki; dysku nie dotyka.
        2. `read_text()` oddaje opis projektu bez komentarzy redakcyjnych.
        3. `read_package_info()` oddaje gałąź i dzień budowy z metryczki.
    """

    def __init__(
        self,
        root: Path,  # np. Path("/code/data/unsafe/code")
    ):
        """
        Description:
        Zapamiętuje katalog paczki. Nie sprawdza, czy pliki istnieją: budowa narzędzi nie dotyka
        dysku, a brak pliku wychodzi przy pierwszym użyciu.

        Example args:
            root=Path("/code/data/unsafe/code")

        Example result:
            CodeDescription czytająca /code/data/unsafe/code/project.md i manifest.json
        """
        self._description = root / DESCRIPTION_FILE
        self._manifest    = root / MANIFEST_FILE

    def read_text(self) -> str:
        """
        Description:
        Oddaje opis projektu z pliku `project.md`: ogólny tekst o tym, z jakich części składa
        się aplikacja i w którym katalogu leży kod której z nich. Bez komentarzy redakcyjnych
        i bez białych znaków na brzegach.

        Example args:
            (brak)

        Example result:
            "Zmyślona aplikacja urzędu na Symfony 1: backend w PHP (akcje modułów w…"

        Raises:
            CodePackageConfigError: opisu projektu nie ma, jest pusty albo nie jest w UTF-8
        """
        try:
            text = read_document(self._description).rstrip()
        except (
            OSError,             # pliku nie ma albo nie da się go otworzyć
            UnicodeDecodeError,  # plik w innym kodowaniu niż UTF-8
        ) as exc:
            raise CodePackageConfigError(
                f"paczka kodu aplikacji nie ma opisu projektu: nie da się odczytać "
                f"{self._description} — opis pisze się ręcznie i leży obok {MANIFEST_FILE}"
            ) from exc

        # Pusty opis wyglądałby dla modelu jak projekt, o którym nie ma nic do powiedzenia.
        if not text:
            raise CodePackageConfigError(
                f"opis projektu w paczce kodu aplikacji jest pusty: {self._description}"
            )

        return text

    def read_package_info(self) -> CodePackageInfo:
        """
        Description:
        Oddaje z metryczki paczki (`manifest.json`) to, co mówi, z której wersji kodu paczka
        powstała: gałąź repozytorium i dzień budowy. Reszty metryczki — liczb plików, listy
        pominiętych — nie czyta.

        Example args:
            (brak)

        Example result:
            CodePackageInfo(branch="/main/stage-gminy", built_on=date(2026, 10, 7))

        Raises:
            CodePackageConfigError: metryczki nie ma albo nie niesie gałęzi i dnia budowy
        """
        try:
            raw  = json.loads(self._manifest.read_text(encoding="utf-8"))
            info = CodePackageInfo(branch=raw["branch"], built_on=raw["built_on"])
        except (
            OSError,               # pliku nie ma albo nie da się go otworzyć
            UnicodeDecodeError,    # plik w innym kodowaniu niż UTF-8
            json.JSONDecodeError,  # plik nie jest JSON-em
            KeyError,              # metryczka bez gałęzi albo bez dnia budowy
            TypeError,             # JSON nie jest obiektem
            ValidationError,       # gałąź albo data w złym kształcie
        ) as exc:
            raise CodePackageConfigError(
                f"metryczka paczki kodu aplikacji jest nie do odczytania: {self._manifest} — "
                f"zbuduj paczkę od nowa (scripts/build_code_package.py)"
            ) from exc

        return info
