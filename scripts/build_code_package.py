"""Buduje paczkę kodu aplikacji, którą czytają narzędzia agenta (CLAUDE.md -> p. 60).

Do czego:
    Kopiuje z folderu z kodem aplikacji pliki wskazane w regułach do podkatalogu `repo/`
    katalogu paczki, po drodze poprawia ich treść i zapisuje obok metryczkę `manifest.json`.
    Kod z paczki idzie do modelu zewnętrznego bez anonimizacji, więc do paczki wchodzi
    wyłącznie to, co reguły wymieniają.

    python scripts/build_code_package.py build /mnt/c/Apache24/htdocs/php74/dokus data/unsafe/code

    Pierwszy argument to folder wejściowy, drugi wyjściowy (katalog paczki); oba są wymagane.

Reguły (`rules.json` w katalogu paczki albo plik podany w `--rules`). Opisują układ kodu
klienta, więc leżą w `data/unsafe/`, poza repo. Ścieżki liczą się od folderu wejściowego:

    | klucz              | znaczenie                                                          |
    |--------------------|--------------------------------------------------------------------|
    | `extensions`       | rozszerzenia brane z folderów z `folders`                          |
    | `folders`          | katalogi kodu własnego, brane w głąb                               |
    | `files`            | pliki wskazane wprost, bez względu na rozszerzenie; `*` zastępuje  |
    |                    | fragment nazwy w obrębie jednego katalogu                          |
    | `excluded_folders` | katalogi pomijane wewnątrz folderów z listy: nazwa bez ukośnika to |
    |                    | katalog na każdej głębokości, wpis z ukośnikiem to jedna ścieżka   |
    | `excluded_files`   | pliki pomijane po samej nazwie, w dowolnym katalogu                |

    Wyłączenie wygrywa ze wszystkim, także z `files`, i nie rozróżnia wielkości liter: `*.min.js`
    obejmuje też `A.MIN.JS`, a `vendor` katalog `Vendor`. Plik, którego reguły nie wymieniają, do
    paczki nie wchodzi; lista takich plików z folderów z listy trafia do metryczki.

Co skrypt zmienia w treści (przykład linii z pliku JS, przed i po):

    msg: 'Nie uda\\u0142o si\\u0119 skomunikowa\\u0107 z serwerem'
    msg: 'Nie udało się skomunikować z serwerem'

    Rozkodowuje tylko polskie litery i tylko w plikach `.js`; w każdym pliku zamienia końce linii
    CRLF na LF. Ścieżki i numery linii zostają takie jak w folderze wejściowym.

Flow:
    1. Czyta reguły (`load_rules`).
    2. Przechodzi po folderach z listy i po plikach wskazanych wprost (`find_files`).
    3. Każdy wybrany plik czyta, poprawia jego treść (`transform`) i zapisuje do katalogu
       tymczasowego (`_add_file`).
    4. Na końcu podmienia `repo/` i zapisuje metryczkę (`build_package`), a w niej gałąź, na
       której stoi folder wejściowy (`read_branch`).

O czym pamiętać przy zmianach:
    - Skrypt kopiuje to, co leży na dysku. Plik prywatny albo lokalnie zmieniony wchodzi do
      paczki, jeśli pasuje do reguł; katalogi z plikami generowanymi w trakcie pracy aplikacji
      (cache, logi) trzeba wyłączyć w regułach.
    - Paczka powstaje w `repo.building/` i zastępuje `repo/` dopiero w komplecie, więc przerwany
      przebieg nie zostawia połowy kodu. Przebieg, po którym paczka byłaby pusta, kończy się
      błędem i poprzedniej paczki nie rusza.
    - Narzędzia czytają paczkę jako UTF-8. Wybrany plik w innym kodowaniu nie wchodzi do
      paczki, a jego ścieżka trafia do metryczki (`skipped.not_utf8`).
    - Sekretu wpisanego w kod PHP albo JS reguły nie widzą; po zmianie reguł trzeba powtórzyć
      przegląd paczki wykrywaczem sekretów.
    - Gałąź w metryczce pochodzi z pliku `.plastic/plastic.selector` folderu wejściowego, czyli
      z kopii roboczej PlasticSCM; skrypt nie rozmawia z repozytorium. Folder bez tego pliku
      (aplikacja syntetyczna) daje metryczkę bez gałęzi. Numeru changesetu metryczka nie ma.
"""

import dataclasses
import datetime
import fnmatch
import json
import os
import pathlib
import re
import shutil

import typer

CODE_DIR      = "repo"
BUILDING_DIR  = "repo.building"
RULES_NAME    = "rules.json"
MANIFEST_NAME = "manifest.json"

# Plik kopii roboczej PlasticSCM, w którym stoi gałąź: linia `smartbranch "/main/…"` albo
# `branch "/main/…"`.
SELECTOR_PATH   = ".plastic/plastic.selector"
SELECTOR_BRANCH = re.compile(r'^\s*(?:smart)?branch\s+"([^"]+)"', re.MULTILINE)

POLISH_LETTERS   = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
ESCAPE_TO_LETTER = {f"{ord(letter):04x}": letter for letter in POLISH_LETTERS}
# Ukośniki przed `u` łapiemy razem z sekwencją: czy to sekwencja, rozstrzyga ich parzystość.
UNICODE_ESCAPE   = re.compile(r"(\\+)u([0-9a-fA-F]{4})")

cli = typer.Typer(help="Budowa paczki kodu aplikacji dla narzędzi agenta.")


@dataclasses.dataclass(frozen=True)
class Rules:
    """Reguły wyboru plików, wczytane z `rules.json`."""

    extensions:       tuple[str, ...]  # np. ("php", "js", "twig")
    folders:          tuple[str, ...]  # np. ("src/apps", "src/lib")
    files:            tuple[str, ...]  # np. ("src/web/*.php",)
    excluded_folders: tuple[str, ...]  # np. ("vendor", "src/web/js/datatables")
    excluded_files:   tuple[str, ...]  # np. ("*.min.js",)


@dataclasses.dataclass
class PackageSize:
    """Ile kodu jest w paczce."""

    files:        int = 0
    lines:        int = 0
    by_extension: dict[str, int] = dataclasses.field(default_factory=dict)  # np. {"php": 10250}


@dataclasses.dataclass
class Changes:
    """Co skrypt zmienił w treści plików."""

    line_endings_files: int = 0  # pliki, w których CRLF zamieniono na LF
    escapes_files:      int = 0  # pliki JS z rozkodowanymi literami
    escapes_lines:      int = 0  # linie zmienione rozkodowaniem


@dataclasses.dataclass
class Skipped:
    """Pliki z folderów z listy, które do paczki nie weszły."""

    not_utf8:     list[str] = dataclasses.field(default_factory=list)  # wybrane, ale nie UTF-8
    not_in_rules: list[str] = dataclasses.field(default_factory=list)  # reguły ich nie biorą


@dataclasses.dataclass
class Manifest:
    """Metryczka paczki: skąd pochodzi kod, ile go jest, co skrypt zmienił i co pominął."""

    source:   str          # np. "/mnt/c/Apache24/htdocs/php74/dokus"
    branch:   str | None   # np. "/main/stage-gminy"; None, gdy folder nie jest kopią roboczą
    built_on: str          # np. "2026-10-06"
    package:  PackageSize
    changes:  Changes
    skipped:  Skipped


def branch_of_selector(
    text: str,  # np. 'repository "dokus@serwer"\n  path "/"\n    smartbranch "/main/stage-gminy"\n'
) -> str | None:
    """
    Description:
    Wyjmuje nazwę gałęzi z treści pliku `plastic.selector`. Oddaje `None`, gdy plik gałęzi nie
    wskazuje: kopia robocza bywa ustawiona na etykietę albo na changeset.

    Example args:
        text='repository "dokus@serwer"\n  path "/"\n    smartbranch "/main/stage-gminy"\n'

    Example result:
        "/main/stage-gminy"
    """
    found = SELECTOR_BRANCH.search(text)

    return found.group(1) if found else None


def read_branch(
    input_dir: pathlib.Path,  # np. Path("/mnt/c/Apache24/htdocs/php74/dokus")
) -> str | None:
    """
    Description:
    Odczytuje gałąź, na której stoi folder wejściowy, z pliku kopii roboczej PlasticSCM. Oddaje
    `None`, gdy folder takiego pliku nie ma — jak źródło aplikacji syntetycznej. Czyta plik
    z dysku i nie rozmawia z repozytorium.

    Example args:
        input_dir=Path("/mnt/c/Apache24/htdocs/php74/dokus")

    Example result:
        "/main/stage-gminy"
    """
    selector = input_dir / SELECTOR_PATH
    if not selector.is_file():
        return None

    # Plik pisze klient PlasticSCM; bajt spoza UTF-8 nie może zatrzymać budowy paczki.
    return branch_of_selector(selector.read_text(encoding="utf-8", errors="replace"))


def load_rules(
    path: pathlib.Path,  # np. Path("data/unsafe/code/rules.json")
) -> Rules:
    """
    Description:
    Wczytuje reguły wyboru plików i sprawdza, że plik ma dokładnie oczekiwane klucze.

    Example args:
        path=Path("data/unsafe/code/rules.json")

    Example result:
        Rules(extensions=("php", "js", "twig"), folders=("src/apps", ...), ...)

    Raises:
        ValueError: gdy w pliku brakuje klucza albo jest klucz nieznany
    """
    raw      = json.loads(path.read_text(encoding="utf-8"))
    expected = {field.name for field in dataclasses.fields(Rules)}
    # Literówka w nazwie klucza dałaby pustą listę, czyli po cichu inną paczkę.
    if set(raw) != expected:
        raise ValueError(f"Reguły w {path} mają klucze {sorted(raw)}, a nie {sorted(expected)}.")
    rules = Rules(
        extensions       = tuple(raw["extensions"]),
        folders          = tuple(raw["folders"]),
        files            = tuple(raw["files"]),
        excluded_folders = tuple(raw["excluded_folders"]),
        excluded_files   = tuple(raw["excluded_files"]),
    )

    return rules


def is_in_excluded_folder(
    path:  str,    # np. "src/lib/vendor/symfony/lib/util/sfFinder.class.php"
    rules: Rules,
) -> bool:
    """
    Description:
    Mówi, czy plik leży w katalogu z `excluded_folders`. Wielkości liter nie rozróżnia.

    Example args:
        path="src/lib/vendor/symfony/lib/util/sfFinder.class.php"
        rules=Rules(excluded_folders=("vendor",), ...)

    Example result:
        True
    """
    # Kod leży na dysku Windows, gdzie `Vendor` i `vendor` to ten sam katalog; rozróżnianie
    # wielkości liter wpuszczałoby do paczki plik, który reguły wyłączają.
    lowered     = path.lower()
    directories = lowered.split("/")[:-1]
    for entry in rules.excluded_folders:
        entry = entry.lower()
        # wpis z ukośnikiem: jedna ścieżka od korzenia, razem ze wszystkim w środku
        if "/" in entry and lowered.startswith(f"{entry}/"):
            return True
        # wpis bez ukośnika: katalog o tej nazwie na każdej głębokości
        if "/" not in entry and entry in directories:
            return True

    return False


def is_excluded(
    path:  str,    # np. "src/web/js/jquery.blockUI.js"
    rules: Rules,
) -> bool:
    """
    Description:
    Mówi, czy plik leży w wyłączonym katalogu albo ma nazwę z `excluded_files`. Wielkości liter
    nie rozróżnia, jak rozszerzenia: `*.min.js` obejmuje też `A.MIN.JS`.

    Example args:
        path="src/web/js/jquery.blockUI.js"
        rules=Rules(excluded_files=("jquery*.js",), ...)

    Example result:
        True
    """
    if is_in_excluded_folder(path, rules):
        return True
    name = path.rsplit("/", 1)[-1].lower()

    return any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in rules.excluded_files)


def is_listed_file(
    path:  str,    # np. "src/apps/frontend/config/routing.yml"
    rules: Rules,
) -> bool:
    """
    Description:
    Mówi, czy plik jest wskazany wprost w `files`. Gwiazdka nie przechodzi przez ukośnik, więc
    `src/web/*.php` nie obejmuje podkatalogów.

    Example args:
        path="src/apps/frontend/config/routing.yml"
        rules=Rules(files=("src/apps/*/config/routing.yml",), ...)

    Example result:
        True
    """
    segments = path.split("/")
    for pattern in rules.files:
        pattern_segments = pattern.split("/")
        if len(pattern_segments) != len(segments):
            continue
        if all(fnmatch.fnmatchcase(s, p) for s, p in zip(segments, pattern_segments, strict=True)):
            return True

    return False


def is_under_folders(
    path:  str,    # np. "src/apps/frontend/config/app.yml"
    rules: Rules,
) -> bool:
    """
    Description:
    Mówi, czy plik leży w którymś z folderów z listy, bez patrzenia na rozszerzenie.

    Example args:
        path="src/apps/frontend/config/app.yml"
        rules=Rules(folders=("src/apps",), ...)

    Example result:
        True
    """
    return any(path.startswith(f"{folder}/") for folder in rules.folders)


def extension_of(
    path: str,  # np. "src/web/js/_global/global.js"
) -> str:
    """
    Description:
    Oddaje rozszerzenie pliku małymi literami, bez kropki; pusty tekst, gdy plik go nie ma.

    Example args:
        path="src/web/js/_global/global.js"

    Example result:
        "js"
    """
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return ""

    return name.rsplit(".", 1)[-1].lower()


def is_taken(
    path:  str,    # np. "src/web/js/_global/global.js"
    rules: Rules,
) -> bool:
    """
    Description:
    Rozstrzyga, czy plik wchodzi do paczki: nie jest wyłączony i albo jest wskazany wprost,
    albo leży w folderze z listy i ma dozwolone rozszerzenie.

    Example args:
        path="src/web/js/_global/global.js"
        rules=Rules(extensions=("js",), folders=("src/web/js",), ...)

    Example result:
        True
    """
    if is_excluded(path, rules):
        return False
    if is_listed_file(path, rules):
        return True

    return extension_of(path) in rules.extensions and is_under_folders(path, rules)


def decode_polish_escapes(
    text: str,  # np. "msg: 'Nie uda\\u0142o si\\u0119'"
) -> tuple[str, int]:
    """
    Description:
    Zamienia sekwencje `\\uXXXX` polskich liter na same litery. Oddaje nowy tekst i liczbę
    zmienionych linii. Inne sekwencje i zapis z parzystą liczbą ukośników zostają bez zmian.

    Example args:
        text="msg: 'Nie uda\\u0142o si\\u0119'"

    Example result:
        ("msg: 'Nie udało się'", 1)
    """
    def replace(match: re.Match[str]) -> str:
        slashes = match.group(1)
        letter  = ESCAPE_TO_LETTER.get(match.group(2).lower())
        # Parzysta liczba ukośników: ostatni jest sam poprzedzony ukośnikiem, więc kod widzi tu
        # ukośnik i zwykły tekst „uXXXX", nie literę.
        if letter is None or len(slashes) % 2 == 0:
            return match.group(0)
        return slashes[:-1] + letter

    lines   = text.split("\n")
    decoded = [UNICODE_ESCAPE.sub(replace, line) for line in lines]
    changed = sum(1 for before, after in zip(lines, decoded, strict=True) if before != after)

    return "\n".join(decoded), changed


def count_lines(
    text: str,  # np. "<?php\necho 1;"
) -> int:
    """
    Description:
    Liczy linie tak jak edytor: ostatnia linia liczy się także bez znaku końca.

    Example args:
        text="<?php\\necho 1;"

    Example result:
        2
    """
    if not text:
        return 0

    return text.count("\n") + (0 if text.endswith("\n") else 1)


def transform(
    path: str,  # np. "src/web/js/_global/global.js"
    text: str,  # np. "var a = '\\u0142';\r\n"
) -> tuple[str, bool, int]:
    """
    Description:
    Poprawia treść pliku przed zapisem do paczki: końce linii CRLF -> LF w każdym pliku,
    polskie litery z `\\uXXXX` tylko w plikach JS. Oddaje nowy tekst, informację, czy zmieniły
    się końce linii, i liczbę linii zmienionych rozkodowaniem.

    Example args:
        path="src/web/js/_global/global.js"
        text="var a = '\\u0142';\\r\\n"

    Example result:
        ("var a = 'ł';\\n", True, 1)
    """
    unix_text       = text.replace("\r\n", "\n")
    endings_changed = unix_text != text
    # W PHP w pojedynczych cudzysłowach ten zapis jest dosłowny, więc poza JS go nie ruszamy.
    if extension_of(path) != "js":
        return unix_text, endings_changed, 0
    decoded, changed_lines = decode_polish_escapes(unix_text)

    return decoded, endings_changed, changed_lines


def find_files(
    input_dir: pathlib.Path,  # np. Path("/mnt/c/Apache24/htdocs/php74/dokus")
    rules:     Rules,
) -> tuple[list[str], list[str]]:
    """
    Description:
    Przechodzi po folderach z listy i po plikach wskazanych wprost. Oddaje dwie posortowane
    listy ścieżek liczonych od folderu wejściowego: pliki, które wchodzą do paczki, oraz pliki
    z folderów z listy, których reguły nie biorą. Do wyłączonych katalogów nie zagląda.

    Example args:
        input_dir=Path("/mnt/c/Apache24/htdocs/php74/dokus")
        rules=Rules(folders=("src/apps",), ...)

    Example result:
        (["src/apps/frontend/config/routing.yml", ...], ["src/apps/frontend/config/app.yml", ...])

    Raises:
        ValueError: gdy folderu z reguł nie ma w folderze wejściowym
    """
    taken     = set()
    not_taken = set()

    # --- foldery z listy, w głąb ---
    for folder in rules.folders:
        # Literówka w nazwie folderu dałaby po cichu mniejszą paczkę.
        if not (input_dir / folder).is_dir():
            raise ValueError(f"Folderu z reguł nie ma w {input_dir}: {folder}")
        for directory, subdirectories, names in os.walk(input_dir / folder):
            relative = pathlib.Path(directory).relative_to(input_dir).as_posix()
            # Przycięcie listy w miejscu sprawia, że os.walk nie wchodzi do wyłączonych katalogów.
            subdirectories[:] = [
                name for name in subdirectories
                if not is_in_excluded_folder(f"{relative}/{name}/_", rules)
            ]
            for name in names:
                path = f"{relative}/{name}"
                (taken if is_taken(path, rules) else not_taken).add(path)

    # --- pliki wskazane wprost; te spoza folderów z listy znajduje tylko ten krok ---
    for pattern in rules.files:
        for found in input_dir.glob(pattern):
            path = found.relative_to(input_dir).as_posix()
            if found.is_file() and is_taken(path, rules):
                taken.add(path)

    return sorted(taken), sorted(not_taken)


def build_package(
    input_dir:  pathlib.Path,  # np. Path("/mnt/c/Apache24/htdocs/php74/dokus")
    output_dir: pathlib.Path,  # np. Path("data/unsafe/code")
    rules:      Rules,
) -> Manifest:
    """
    Description:
    Buduje paczkę: wybiera pliki według reguł, kopiuje je z poprawioną treścią, podmienia
    `repo/` i zapisuje metryczkę.

    Example args:
        input_dir=Path("/mnt/c/Apache24/htdocs/php74/dokus")
        output_dir=Path("data/unsafe/code")
        rules=Rules(...)

    Example result:
        Manifest(source="/mnt/c/.../dokus", branch="/main/stage-gminy", built_on="2026-10-06",
                 package=PackageSize(...), ...)

    Raises:
        ValueError: gdy folderu z reguł nie ma, katalog docelowy nie jest paczką albo do paczki
            nie wszedł żaden plik
    """
    code_dir      = output_dir / CODE_DIR
    building_dir  = output_dir / BUILDING_DIR
    manifest_path = output_dir / MANIFEST_NAME

    # --- nie kasujemy katalogu, którego ten skrypt nie zbudował ---
    if code_dir.exists() and not manifest_path.exists():
        raise ValueError(f"{code_dir} istnieje, ale obok nie ma {MANIFEST_NAME}; nie kasuję go.")

    taken, not_taken = find_files(input_dir, rules)
    typer.echo(f"Wybranych regułami: {len(taken)} plików")
    manifest = Manifest(
        source   = str(input_dir),
        branch   = read_branch(input_dir),
        built_on = datetime.date.today().isoformat(),
        package  = PackageSize(),
        changes  = Changes(),
        skipped  = Skipped(not_in_rules=not_taken),
    )

    # --- kopiowanie do katalogu tymczasowego; pozostałość po przerwanym przebiegu znika ---
    output_dir.mkdir(parents=True, exist_ok=True)
    if building_dir.exists():
        shutil.rmtree(building_dir)
    for index, path in enumerate(taken, start=1):
        _add_file(building_dir, path, (input_dir / path).read_bytes(), manifest)
        if index % 2000 == 0 or index == len(taken):
            typer.echo(f"  {index}/{len(taken)}")

    # --- pusta paczka to błąd reguł albo kodowania, nie wynik: poprzedniej nie ruszamy ---
    if manifest.package.files == 0:
        not_utf8 = len(manifest.skipped.not_utf8)
        raise ValueError(
            f"Do paczki nie wszedł żaden plik (wybranych regułami: {len(taken)}, "
            f"nie w UTF-8: {not_utf8}); {code_dir} zostaje bez zmian."
        )

    # --- podmiana dopiero z kompletem plików w ręku ---
    if code_dir.exists():
        shutil.rmtree(code_dir)
    building_dir.rename(code_dir)
    manifest_json = json.dumps(dataclasses.asdict(manifest), ensure_ascii=False, indent=2)
    manifest_path.write_text(f"{manifest_json}\n", encoding="utf-8")

    return manifest


def _add_file(
    building_dir: pathlib.Path,  # np. Path("data/unsafe/code/repo.building")
    path:         str,           # np. "src/web/js/_global/global.js"
    content:      bytes,         # np. b"var a = 1;\r\n"
    manifest:     Manifest,
) -> None:
    """
    Description:
    Zapisuje jeden plik do budowanej paczki i dopisuje go do liczników metryczki. Plik, który
    nie jest w UTF-8, pomija i odnotowuje: narzędzia czytają paczkę jako UTF-8.

    Example args:
        building_dir=Path("data/unsafe/code/repo.building")
        path="src/web/js/_global/global.js"
        content=b"var a = 1;\\r\\n"
        manifest=Manifest(...)

    Example result:
        None (plik na dysku, liczniki w `manifest`)
    """
    # Kodowania nie zgadujemy: bajty, które nie są poprawnym UTF-8, to plik pominięty.
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        manifest.skipped.not_utf8.append(path)
        return

    new_text, endings_changed, escape_lines = transform(path, text)
    target = building_dir / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(new_text.encode("utf-8"))

    extension = extension_of(path)
    package   = manifest.package
    changes   = manifest.changes
    package.files                   += 1
    package.lines                   += count_lines(new_text)
    package.by_extension[extension]  = package.by_extension.get(extension, 0) + 1
    changes.line_endings_files      += int(endings_changed)
    changes.escapes_files           += int(escape_lines > 0)
    changes.escapes_lines           += escape_lines


@cli.callback()
def main() -> None:
    """
    Description:
    Grupuje subkomendy, żeby Typer zachował drzewo komend także przy jednej komendzie.

    Example args:
        (brak)

    Example result:
        None
    """


# Teksty pomocy w stałych, a nie w docstringach: inaczej Typer wstawi do `--help` opis pisany
# dla programisty (CLAUDE.md -> „Warstwa CLI").
HELP_COMMAND = "Buduje paczkę kodu z folderu z kodem aplikacji według reguł z pliku rules.json."
HELP_INPUT   = "Folder z kodem aplikacji; od niego liczą się ścieżki w regułach."
HELP_OUTPUT  = "Katalog paczki: powstaje w nim repo/ z kodem i manifest.json."
HELP_RULES   = "Plik reguł wyboru plików; domyślnie rules.json w katalogu paczki."


@cli.command(help=HELP_COMMAND)
def build(
    input_dir:  pathlib.Path        = typer.Argument(...,           help=HELP_INPUT),
    output_dir: pathlib.Path        = typer.Argument(...,           help=HELP_OUTPUT),
    rules_path: pathlib.Path | None = typer.Option(None, "--rules", help=HELP_RULES),
) -> None:
    """
    Description:
    Buduje paczkę kodu i wypisuje podsumowanie: ile plików weszło i co skrypt w nich zmienił.

    Example args:
        input_dir=Path("/mnt/c/Apache24/htdocs/php74/dokus")
        output_dir=Path("data/unsafe/code")
        rules_path=None

    Example result:
        None (paczka na dysku + podsumowanie na stdout)

    Raises:
        typer.Exit: gdy nie ma folderu wejściowego albo pliku reguł, albo reguły są błędne
    """
    # --- fail-fast: oba wejścia muszą istnieć, zanim cokolwiek ruszymy ---
    if not input_dir.is_dir():
        typer.echo(f"Nie ma folderu wejściowego: {input_dir}", err=True)
        raise typer.Exit(code=1)
    rules_file = rules_path or output_dir / RULES_NAME
    if not rules_file.is_file():
        typer.echo(f"Nie ma pliku reguł: {rules_file}", err=True)
        raise typer.Exit(code=1)

    try:
        manifest = build_package(input_dir, output_dir, load_rules(rules_file))
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    package = manifest.package
    changes = manifest.changes
    typer.echo(f"Paczka: {package.files} plików, {package.lines} linii w {output_dir / CODE_DIR}")
    typer.echo(f"  gałąź folderu wejściowego: {manifest.branch or 'brak (nie kopia robocza)'}")
    typer.echo(f"  wg rozszerzeń: {package.by_extension}")
    typer.echo(f"  końce linii zamienione w plikach: {changes.line_endings_files}")
    typer.echo(f"  litery z \\uXXXX rozkodowane: {changes.escapes_lines} linii "
               f"w {changes.escapes_files} plikach")
    typer.echo(f"  pominięte, bo nie UTF-8: {len(manifest.skipped.not_utf8)}")
    typer.echo(f"  w folderach z listy, ale poza regułami: {len(manifest.skipped.not_in_rules)}")


if __name__ == "__main__":
    cli()
