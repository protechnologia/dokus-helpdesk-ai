"""
Description:
Czyta pliki z paczki kodu aplikacji i pilnuje, żeby ścieżka podana przez model nie wyszła poza
paczkę. Paczka to katalog zbudowany przez `scripts/build_code_package.py`: kod leży w `repo/`,
obok stoi `manifest.json`. Nie woła żadnej usługi — kod zostaje w folderze, bez bazy.

Przed — ścieżka od modelu:

    "src/lib/Urzad/Sesja/../Numeracja/GeneratorNumeru.php"

Po — ścieżka w paczce i linie pliku:

    package.locate(…)      →  "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
    package.read_lines(…)  →  ["<?php", "", "namespace Urzad\\Numeracja;", …]

Szukanie w kodzie przyjmuje też katalog, więc `locate()` ma flagę `allow_dir`:

    package.locate("src/web/../web/js", allow_dir=True)  →  "src/web/js"

Co jest sprawdzane:

| co                                                     | wynik                    |
|--------------------------------------------------------|--------------------------|
| katalogu paczki albo jej `repo/` nie ma                | `CodePackageConfigError` |
| ścieżka wychodzi poza `repo/` (`..`, dowiązanie)       | `CodePathError`          |
| pod ścieżką jest katalog, a flagi `allow_dir` nie ma   | `CodePathError`          |
| pod ścieżką nic nie ma albo nie da się jej odczytać    | `CodePathError`          |

O czym pamiętać przy zmianach:

- Ścieżkę podaje model, więc granicy pilnuje się na ścieżce ROZWIĄZANEJ: po zdjęciu `..`
  i dowiązań musi leżeć w `repo/`. Porównanie samego napisu przepuściłoby dowiązanie.
- Komunikat `CodePathError` wraca do modelu, więc powtarza ścieżkę tak, jak ją podał, i nie
  zdradza, gdzie paczka leży na dysku.
- Brak paczki to błąd wdrożenia, nie ścieżki: bez tego rozróżnienia model dostawałby „nie ma
  takiego pliku" na każde pytanie i uznawał, że kod nic nie mówi.
- Linie dzieli wyłącznie `\\n`, jak w ripgrepie i w edytorze (`split_lines()`); tą samą funkcją
  liczą linie atrapy narzędzi kodu, żeby numery znaczyły to samo w testach i na paczce.
- Paczka jest w UTF-8 i ma końce linii LF: skrypt paczki pomija pliki w innym kodowaniu
  i zamienia CRLF.
- Samo szukanie tu nie mieszka: robi je program ripgrep, uruchamiany przez `engine_process/`.
  Stąd dostaje katalog z kodem (`repo_dir()`) i ścieżkę już sprawdzoną (`locate()`).
"""

from pathlib import Path

# Podkatalog paczki z kodem; obok niego stoi metryczka `manifest.json`.
REPO_DIR = "repo"


class CodePackageConfigError(Exception):
    """
    Description:
    Paczki kodu nie ma tam, gdzie wskazuje konfiguracja (`CODE_PACKAGE_DIR`): katalog nie
    istnieje albo nie ma w nim `repo/`.

    Błąd wdrożenia, a nie wywołania: poprawiona ścieżka niczego by nie zmieniła, więc do modelu
    nie wraca i zatrzymuje przebieg.
    """


class CodePathError(Exception):
    """
    Description:
    Ścieżka nie wskazuje pliku w paczce kodu: wychodzi poza paczkę, prowadzi do katalogu albo
    donikąd. Komunikat powtarza ścieżkę w brzmieniu od wołającego i nadaje się do pokazania
    modelowi.
    """


def split_lines(
    text: str,  # np. "<?php\n\nclass GeneratorNumeru\n"
) -> list[str]:
    """
    Description:
    Dzieli treść pliku na linie tak, jak liczy je ripgrep i edytor: wyłącznie na `\n`, a znak
    końca linii na końcu pliku nie otwiera jeszcze jednej, pustej. Linia numer N to element N-1.

    Nie `str.splitlines()`: ono tnie też na znaku końca strony i kilku innych, więc numery linii
    rozjechałyby się z wynikami szukania.

    Example args:
        text="<?php\n\nclass GeneratorNumeru\n"

    Example result:
        ["<?php", "", "class GeneratorNumeru"]
    """
    lines = text.split("\n")

    # Plik zakończony znakiem końca linii nie ma po nim jeszcze jednej, pustej.
    if lines[-1] == "":
        lines.pop()

    return lines


class CodePackage:
    """
    Description:
    Paczka kodu aplikacji na dysku: znajduje w niej plik po ścieżce i oddaje jego linie.

    Do czego:
    Na niej stoją narzędzia agenta czytające kod (`agent_tools/code/`), tak jak narzędzia
    dokumentacji stoją na tabeli w Postgresie. Narzędzie dostaje paczkę w konstruktorze i nie
    składa ścieżek samo, więc granicy paczki pilnuje jedno miejsce. Tylko do odczytu.

    Flow:
        1. Konstruktor zapamiętuje katalog paczki; dysku nie dotyka.
        2. `locate()` sprawdza ścieżkę i oddaje ją w postaci względnej wobec `repo/`.
        3. `read_lines()` oddaje linie znalezionego pliku, bez znaków końca linii.
        4. `repo_dir()` oddaje katalog z kodem temu, kto w nim szuka.
    """

    def __init__(
        self,
        root: Path,  # np. Path("/code/data/unsafe/code")
    ):
        """
        Description:
        Zapamiętuje katalog paczki. Nie sprawdza, czy istnieje: budowa narzędzi nie dotyka
        dysku, a brak paczki wychodzi przy pierwszym użyciu.

        Example args:
            root=Path("/code/data/unsafe/code")

        Example result:
            CodePackage czytająca pliki z /code/data/unsafe/code/repo
        """
        self._repo = root / REPO_DIR

    def locate(
        self,
        path:      str,          # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        *,                       # flagę podaje się wyłącznie po nazwie
        allow_dir: bool = False, # True: ścieżka może wskazywać także katalog
    ) -> str:
        """
        Description:
        Sprawdza, czy ścieżka wskazuje plik w paczce, i oddaje ją w jednej postaci: względną
        wobec `repo/`, bez `..` i podwójnych ukośników. W tej postaci ścieżka służy za
        identyfikator, więc dwa zapisy tego samego pliku dają ten sam.

        Z `allow_dir=True` przyjmuje też katalog — do zawężania szukania, które bierze jedno
        i drugie. Wynikiem bywa wtedy ścieżka katalogu, a sam katalog z kodem wraca jako `"."`,
        więc takiego wyniku nie podaje się do `read_lines()`.

        Example args:
            path="src/lib/Urzad/Sesja/../Numeracja/GeneratorNumeru.php"
            allow_dir=False

        Example result:
            "src/lib/Urzad/Numeracja/GeneratorNumeru.php"

        Raises:
            CodePathError: ścieżka wychodzi poza paczkę, wskazuje katalog (bez `allow_dir`)
                albo nic nie wskazuje
            CodePackageConfigError: paczki nie ma pod skonfigurowaną ścieżką
        """
        repo    = self.repo_dir()
        missing = "nie ma takiego pliku ani katalogu" if allow_dir else "nie ma takiego pliku"

        # --- rozwiązanie ścieżki: po zdjęciu `..` i dowiązań widać, dokąd naprawdę prowadzi ---
        try:
            target  = (repo / path).resolve()
            inside  = target.is_relative_to(repo)
            is_dir  = inside and target.is_dir()
            is_file = inside and target.is_file()
        except (
            ValueError,  # znak zerowy w ścieżce
            OSError,     # np. nazwa dłuższa, niż przyjmuje system plików
        ):
            raise CodePathError(f"{missing} w kodzie aplikacji: {path!r}") from None

        # --- poza paczką: nie mówimy, czy pod ścieżką coś jest ---
        if not inside:
            raise CodePathError(f"ścieżka wychodzi poza kod aplikacji: {path}")

        # --- katalog: cytuje się i czyta pliki; przyjmuje go tylko szukanie ---
        if is_dir and not allow_dir:
            raise CodePathError(f"to katalog, nie plik: {path}")

        # --- nic albo coś, co nie jest zwykłym plikiem ani katalogiem ---
        if not is_dir and not is_file:
            raise CodePathError(f"{missing} w kodzie aplikacji: {path}")

        return target.relative_to(repo).as_posix()

    def read_lines(
        self,
        path: str,  # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
    ) -> list[str]:
        """
        Description:
        Oddaje linie pliku z paczki, bez znaków końca linii. Linia numer N w pliku to element
        N-1 listy.

        Example args:
            path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"

        Example result:
            ["<?php", "", "namespace Urzad\\Numeracja;", …]

        Raises:
            CodePathError: ścieżka wychodzi poza paczkę, wskazuje katalog albo nic nie wskazuje
            CodePackageConfigError: paczki nie ma pod skonfigurowaną ścieżką
        """
        located = self.locate(path)
        text    = (self.repo_dir() / located).read_text(encoding="utf-8")

        return split_lines(text)

    def repo_dir(self) -> Path:
        """
        Description:
        Oddaje katalog `repo/` paczki w postaci rozwiązanej: do porównań ze ścieżkami plików
        i jako katalog, w którym szuka program uruchamiany przez `engine_process/`.
        Sprawdzany przy każdym użyciu, bo paczkę podmienia się przebudową, bez restartu usługi.

        Example args:
            (brak)

        Example result:
            Path("/code/data/unsafe/code/repo")

        Raises:
            CodePackageConfigError: katalogu paczki albo jej `repo/` nie ma
        """
        if not self._repo.is_dir():
            raise CodePackageConfigError(
                f"brak paczki kodu aplikacji: {self._repo} nie jest katalogiem — sprawdź "
                f"CODE_PACKAGE_DIR i zbuduj paczkę (scripts/build_code_package.py)"
            )

        return self._repo.resolve()
