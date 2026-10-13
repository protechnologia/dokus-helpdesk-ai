"""Buduje mapę symboli paczki kodu aplikacji: gdzie zaczyna się i kończy każda funkcja, metoda
i klasa (CLAUDE.md -> p. 66).

Do czego:
    Czyta pliki PHP i JS z `repo/` w katalogu paczki, rozbiera je parserem tree-sitter
    i zapisuje obok metryczki plik `symbols.json`: dla każdego pliku listę definicji z pierwszą
    i ostatnią linią. Z mapy narzędzia agenta wezmą granice funkcji, żeby model mógł przeczytać
    jedną funkcję w całości, zamiast zgadywać zakres linii (p. 73).

    python scripts/build_code_symbols.py build data/unsafe/code

    Budowa paczki (`build_code_package.py build`) robi to samo na końcu. Osobna komenda
    dobudowuje mapę do paczki, która już stoi, bez kopiowania kodu od nowa.

Co jest symbolem. W mapie są same DEFINICJE; użyć (wywołań) w niej nie ma:

    | język | zapis w kodzie                               | `kind`      | `scope`      |
    |-------|----------------------------------------------|-------------|--------------|
    | PHP   | `class`, `interface`, `trait`                | jak w kodzie | brak        |
    | PHP   | metoda klasy, interfejsu albo traitu         | `method`    | nazwa klasy  |
    | PHP   | funkcja poza klasą                           | `function`  | brak         |
    | JS    | `function nazwa() {}`                        | `function`  | brak         |
    | JS    | `var nazwa = function () {}`                 | `function`  | brak         |
    | JS    | `A.b.nazwa = function () {}`                 | `function`  | `A.b`        |
    | JS    | `nazwa: function () {}` w obiekcie pod `A.b` | `function`  | `A.b`        |
    | JS    | `class Nazwa {}`                             | `class`     | brak         |
    | JS    | metoda klasy                                 | `method`    | nazwa klasy  |

Przykład — plik JS z aplikacji syntetycznej i jego wpis w mapie:

    1  // Handlery modułu pism; wołane przez APP.zdarzenia po kliknięciu elementu…
    2  APP.pisma = {
    3      zapiszHandler: function (parametry) {
    4          $.post('/pisma/zapisz', { id: parametry.id }).done(function (wynik) {
    5              $('#numer-pisma').text(wynik.numer);
    6          });
    7      },
    8
    9      wyslijHandler: function (parametry) {
    …
    17     }
    18 };

    "src/web/js/pisma/pisma.js": [
     {"name": "zapiszHandler", "scope": "APP.pisma", "kind": "function",
      "from_line": 3, "to_line": 7},
     {"name": "wyslijHandler", "scope": "APP.pisma", "kind": "function",
      "from_line": 9, "to_line": 17}]

    Funkcja z linii 4, podana jako argument `done()`, nie ma własnego wpisu: leży w ciele
    `zapiszHandler` i do niej należy. W pliku wpis zajmuje jedną linię.

Flow:
    1. Kasuje poprzednią mapę, żeby przerwany przebieg nie zostawił mapy starego kodu
       (`build_symbols`).
    2. Przechodzi po plikach `.php` i `.js` paczki i każdy rozbiera (`symbols_of_file`).
    3. Z drzewa składni wybiera definicje (`php_symbols`, `js_symbols`).
    4. Zapisuje `symbols.json`, linia na plik (`symbols_as_json`), i wypisuje podsumowanie
       (`report_symbols`).

O czym pamiętać przy zmianach:
    - Definicja w ciele funkcji albo metody nie jest osobnym symbolem. W JS to głównie funkcje
      podawane jako argument (`success`, `click`): w jednym pliku powtarzają się dziesiątki
      razy, a czyta się je razem z funkcją, w której leżą. Funkcja bez nazwy, która tylko
      opakowuje plik (`$(function () { … })`), symbolem nie jest, więc definicje w jej ciele
      trafiają do mapy.
    - `scope` w JS powstaje tylko z prostej ścieżki nazw (`A.b`, `this`, `A.prototype`).
      Obiekt podany wprost jako argument wywołania nie ma nazwy, więc jego funkcje mają
      `scope` puste.
    - Plik, w którym parser zgłasza błąd składni, nie dostaje ŻADNEGO symbolu i trafia na
      listę `syntax_errors`. Parser po błędzie czyta dalej, ale granic funkcji z takiego
      pliku nie da się już ręczyć, a narzędzie ma oddawać funkcję w całości. Błąd bywa też
      luką parsera w poprawnym kodzie (stała klasy o nazwie `NAMESPACE`).
    - Linie liczy się od 1, obie granice należą do symbolu, a dzieli je wyłącznie znak nowej
      linii — tak samo jak w ripgrepie i w czytniku paczki, więc numery z mapy, z szukania
      i z odczytu znaczą to samo.
    - Symbol zaczyna się w linii swojej definicji. Komentarz nad funkcją do niej nie należy.
    - Kod zapisany jako tekst definicją nie jest: metoda w szablonie, z którego generator
      dopiero składa klasę, i funkcja JS wypisywana z pliku PHP symboli nie mają.
    - Mapa opisuje dokładnie ten kod, z którego powstała. Po ręcznej zmianie `repo/` trzeba ją
      zbudować od nowa; czytnik w `api` (`core_service/loader_code_symbols.py`) tego nie
      wykryje.
    - tree-sitter jest tylko w `requirements-dev.txt`: obraz `api` czyta gotową mapę i kodu
      nie rozbiera.
"""

import dataclasses
import datetime
import json
import pathlib
import re

import tree_sitter_javascript
import tree_sitter_php
import typer
from tree_sitter import Language, Node, Parser

CODE_DIR     = "repo"
SYMBOLS_NAME = "symbols.json"

# `language_php()` rozbiera plik w całości, razem z HTML-em wokół `<?php … ?>`: szablony
# Symfony mieszają jedno z drugim.
PARSERS = {
    "php": Parser(Language(tree_sitter_php.language_php())),
    "js":  Parser(Language(tree_sitter_javascript.language())),
}

# Węzły PHP, które niosą metody, i słowo, pod którym trafiają do mapy.
PHP_CLASS_KINDS = {
    "class_declaration":     "class",
    "interface_declaration": "interface",
    "trait_declaration":     "trait",
}
# Węzły PHP z ciałem funkcji: w ich wnętrzu definicji już nie szukamy.
PHP_FUNCTION_KINDS = {
    "method_declaration":  "method",
    "function_definition": "function",
}

# Wartość, która robi z przypisania albo pola obiektu definicję funkcji w JS.
JS_FUNCTION_VALUES = ("function_expression", "arrow_function")

# Prosta ścieżka nazw w JS: `APP`, `APP.pisma`, `this`, `$.fn`.
PLAIN_PATH = re.compile(r"[\w$]+(\.[\w$]+)*")

cli = typer.Typer(help="Budowa mapy symboli paczki kodu aplikacji.")


@dataclasses.dataclass(frozen=True)
class Symbol:
    """Jedna definicja w pliku: nazwa, w czym leży, czym jest i w których liniach stoi."""

    name:      str         # np. "nastepnyNumer"
    scope:     str | None  # np. "GeneratorNumeru"; None: definicja nie leży w niczym nazwanym
    kind:      str         # "class" | "interface" | "trait" | "method" | "function"
    from_line: int         # pierwsza linia definicji, liczona od 1
    to_line:   int         # ostatnia linia definicji, włącznie


@dataclasses.dataclass
class SymbolMap:
    """Mapa symboli paczki — treść pliku `symbols.json`."""

    built_on:      str                                                         # np. "2026-10-13"
    # Tylko pliki, w których jest choć jedna definicja; ścieżki liczone od `repo/`.
    files:         dict[str, list[Symbol]] = dataclasses.field(default_factory=dict)
    # Pliki PHP i JS, których parser nie rozebrał bez błędu: w mapie nie mają symboli.
    syntax_errors: list[str]               = dataclasses.field(default_factory=list)


def _symbol(
    node:  Node,        # węzeł całej definicji, np. `method_declaration`
    name:  str,         # np. "nastepnyNumer"
    scope: str | None,  # np. "GeneratorNumeru"
    kind:  str,         # np. "method"
) -> Symbol:
    """
    Description:
    Składa wpis mapy z węzła drzewa składni. Parser liczy wiersze od zera, mapa od jedynki.

    Example args:
        node=<method_declaration, wiersze 12–25>
        name="nastepnyNumer"
        scope="GeneratorNumeru"
        kind="method"

    Example result:
        Symbol(name="nastepnyNumer", scope="GeneratorNumeru", kind="method",
               from_line=13, to_line=26)
    """
    # Wiersz bierzemy indeksem `[0]`, nie atrybutem `.row`: w tree-sitter 0.26.0 odczyt atrybutu
    # psuje pamięć procesu — w pliku na 441 linii wychodziły numery -257 i 257, a potem
    # proces kończył się błędem pamięci.
    symbol = Symbol(
        name      = name,
        scope     = scope,
        kind      = kind,
        from_line = node.start_point[0] + 1,
        to_line   = node.end_point[0] + 1,
    )

    return symbol


def _text(
    node: Node,  # np. węzeł nazwy metody
) -> str:
    """
    Description:
    Oddaje tekst węzła tak, jak stoi w pliku.

    Example args:
        node=<name "nastepnyNumer">

    Example result:
        "nastepnyNumer"
    """
    return node.text.decode("utf-8", errors="replace")


def _in_order(
    symbols: list[Symbol],
) -> list[Symbol]:
    """
    Description:
    Układa symbole pliku w kolejności kodu: po pierwszej linii, a przy tej samej dłuższy
    najpierw — klasa stoi przed swoją pierwszą metodą.

    Example args:
        symbols=[Symbol("nastepnyNumer", …, 13, 26), Symbol("GeneratorNumeru", …, 8, 27)]

    Example result:
        [Symbol("GeneratorNumeru", …, 8, 27), Symbol("nastepnyNumer", …, 13, 26)]
    """
    return sorted(symbols, key=lambda symbol: (symbol.from_line, -symbol.to_line))


def php_symbols(
    root: Node,  # korzeń drzewa składni pliku PHP
) -> list[Symbol]:
    """
    Description:
    Wybiera z drzewa składni pliku PHP definicje klas, interfejsów, traitów, metod i funkcji.
    Metoda dostaje w `scope` nazwę klasy, w której leży. W ciało metody ani funkcji nie
    schodzi: funkcja bez nazwy i klasa anonimowa wewnątrz metody należą do tej metody.

    Example args:
        root=<program: class GeneratorNumeru { public function nastepnyNumer($rok) {…} }>

    Example result:
        [Symbol("GeneratorNumeru", None, "class", 8, 27),
         Symbol("nastepnyNumer", "GeneratorNumeru", "method", 13, 26)]
    """
    symbols: list[Symbol] = []
    # Bez rekurencji: długie wyrażenie daje drzewo głębsze niż limit rekurencji Pythona.
    pending: list[tuple[Node, str | None]] = [(root, None)]

    while pending:
        node, scope = pending.pop()

        # --- klasa, interfejs, trait: wpis, a jej metody dostają jej nazwę ---
        if node.type in PHP_CLASS_KINDS:
            name = _text(node.child_by_field_name("name"))
            symbols.append(_symbol(node, name, None, PHP_CLASS_KINDS[node.type]))
            pending.extend((child, name) for child in node.children)
            continue

        # --- metoda albo funkcja: wpis, a w jej ciało nie schodzimy ---
        if node.type in PHP_FUNCTION_KINDS:
            name = _text(node.child_by_field_name("name"))
            symbols.append(_symbol(node, name, scope, PHP_FUNCTION_KINDS[node.type]))
            continue

        # --- każdy inny węzeł: definicje mogą leżeć głębiej (blok `if`, przestrzeń nazw) ---
        pending.extend((child, scope) for child in node.children)

    return _in_order(symbols)


def _js_key(
    key: Node,  # klucz pola obiektu
) -> str | None:
    """
    Description:
    Oddaje nazwę pola obiektu JS: zwykłą albo zapisaną w cudzysłowie. Klucz wyliczany
    (`[zmienna]: …`) nazwy nie ma.

    Example args:
        key=<string "'Zapisz'">

    Example result:
        "Zapisz"
    """
    # --- nazwa bez cudzysłowu albo liczba ---
    if key.type in ("property_identifier", "number"):
        return _text(key)

    # --- napis: sama treść, bez cudzysłowów ---
    if key.type == "string":
        return _text(key)[1:-1] or None

    # --- klucz wyliczany w trakcie działania ---
    return None


def _js_name_and_scope(
    target: Node,  # to, do czego przypisano funkcję albo obiekt
) -> tuple[str | None, str | None]:
    """
    Description:
    Rozkłada lewą stronę przypisania w JS na nazwę i to, w czym nazwa leży. Lewa strona,
    której nie da się tak rozłożyć (`tablica[i]`, wynik wywołania), nie daje nazwy.

    Example args:
        target=<member_expression "OBI.sprawy.errorHandler">

    Example result:
        ("errorHandler", "OBI.sprawy")
    """
    # --- sama nazwa: `var obsluga = function …`, `obsluga = function …` ---
    if target.type == "identifier":
        return _text(target), None

    # --- ścieżka z kropką: ostatni człon to nazwa, reszta to miejsce ---
    if target.type == "member_expression":
        owner  = target.child_by_field_name("object")
        member = target.child_by_field_name("property")
        # Pole prywatne klasy (`this.#pole`) nazwy dla mapy nie daje.
        if member.type != "property_identifier":
            return None, None
        scope = _text(owner)

        # Miejsce inne niż prosta ścieżka (`$(this).data('x')`) nie nadaje się na nazwę.
        return _text(member), scope if PLAIN_PATH.fullmatch(scope) else None

    # --- wszystko inne: indeks tablicy, destrukturyzacja ---
    return None, None


def js_symbols(
    root: Node,  # korzeń drzewa składni pliku JS
) -> list[Symbol]:
    """
    Description:
    Wybiera z drzewa składni pliku JS definicje funkcji i klas. Funkcją jest deklaracja
    `function`, przypisanie funkcji do nazwy albo ścieżki oraz pole obiektu z funkcją.
    `scope` niesie to, pod czym definicja leży: ścieżkę z lewej strony przypisania, nazwę
    obiektu, do którego należy pole, albo nazwę klasy.

    W ciało funkcji, która trafiła do mapy, nie schodzi. Funkcja bez nazwy do mapy nie
    trafia, więc definicje w jej ciele są wybierane jak każde inne.

    Example args:
        root=<program: APP.pisma = { zapiszHandler: function (parametry) {…} };>

    Example result:
        [Symbol("zapiszHandler", "APP.pisma", "function", 3, 7)]
    """
    symbols: list[Symbol] = []
    # Para: węzeł i nazwa obiektu albo klasy, do której należą jego pola. Nazwę dostaje
    # wyłącznie węzeł obiektu albo ciała klasy; każdy inny jej nie przenosi.
    pending: list[tuple[Node, str | None]] = [(root, None)]

    while pending:
        node, scope = pending.pop()

        # --- function nazwa() {} ---
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                symbols.append(_symbol(node, _text(name_node), None, "function"))
                continue

        # --- class Nazwa { … }: wpis, a metody dostają nazwę klasy ---
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            body      = node.child_by_field_name("body")
            if name_node is not None and body is not None:
                symbols.append(_symbol(node, _text(name_node), None, "class"))
                pending.append((body, _text(name_node)))
                continue

        # --- metoda klasy albo funkcja zapisana w obiekcie skrótem `nazwa() {}` ---
        if node.type == "method_definition":
            name = _js_key(node.child_by_field_name("name"))
            if name is not None:
                kind = "method" if node.parent.type == "class_body" else "function"
                symbols.append(_symbol(node, name, scope, kind))
                continue

        # --- pole obiektu: funkcja to wpis, obiekt przekazuje nazwę głębiej ---
        if node.type == "pair":
            name  = _js_key(node.child_by_field_name("key"))
            value = node.child_by_field_name("value")
            if name is not None and value.type in JS_FUNCTION_VALUES:
                symbols.append(_symbol(node, name, scope, "function"))
                continue
            if name is not None and value.type == "object" and scope is not None:
                pending.append((value, f"{scope}.{name}"))
                continue

        # --- przypisanie i deklaracja zmiennej: nazwa stoi po lewej stronie ---
        if node.type in ("assignment_expression", "variable_declarator"):
            is_assignment = node.type == "assignment_expression"
            target        = node.child_by_field_name("left" if is_assignment else "name")
            value         = node.child_by_field_name("right" if is_assignment else "value")
            name, owner   = _js_name_and_scope(target)
            if name is not None and value is not None and value.type in JS_FUNCTION_VALUES:
                symbols.append(_symbol(node, name, owner, "function"))
                continue
            if name is not None and value is not None and value.type == "object":
                pending.append((value, f"{owner}.{name}" if owner else name))
                continue

        # --- obiekt i ciało klasy podają swoją nazwę polom; inne węzły jej nie przenoszą ---
        inherited = scope if node.type in ("object", "class_body") else None
        pending.extend((child, inherited) for child in node.children)

    return _in_order(symbols)


def language_of(
    path: str,  # np. "src/web/js/pisma/pisma.js"
) -> str | None:
    """
    Description:
    Rozpoznaje język pliku po rozszerzeniu, bez względu na wielkość liter. Mapa obejmuje PHP
    i JS; szablony Twig, YAML i XML z paczki symboli nie mają.

    Example args:
        path="src/web/js/pisma/pisma.js"

    Example result:
        "js"
    """
    extension = path.rsplit(".", 1)[-1].lower() if "." in path else ""

    return extension if extension in PARSERS else None


def symbols_of_file(
    path:    str,    # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
    content: bytes,  # treść pliku
) -> list[Symbol] | None:
    """
    Description:
    Oddaje definicje z jednego pliku PHP albo JS, w kolejności kodu. `None` znaczy, że parser
    zgłosił w pliku błąd składni: taki plik nie dostaje żadnego symbolu.

    Example args:
        path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        content=b"<?php\\n\\nclass GeneratorNumeru\\n{…"

    Example result:
        [Symbol("GeneratorNumeru", None, "class", 8, 27),
         Symbol("nastepnyNumer", "GeneratorNumeru", "method", 13, 26)]

    Raises:
        ValueError: plik w języku, którego mapa nie obejmuje
    """
    language = language_of(path)
    if language is None:
        raise ValueError(f"Mapa symboli nie obejmuje plików tego rodzaju: {path}")

    # Drzewo trzyma zmienna do końca funkcji: węzły nie utrzymują go przy życiu, a przejście
    # po węzłach zwolnionego drzewa kończy proces błędem pamięci.
    tree = PARSERS[language].parse(content)
    # Błąd gdziekolwiek w pliku: granice funkcji mogą być przesunięte, więc nie bierzemy żadnej.
    if tree.root_node.has_error:
        return None
    symbols = php_symbols(tree.root_node) if language == "php" else js_symbols(tree.root_node)

    return symbols


def symbols_as_json(
    symbol_map: SymbolMap,
) -> str:
    """
    Description:
    Zapisuje mapę jako JSON, w którym każdy plik kodu zajmuje jedną linię. Dzięki temu
    `grep nazwa symbols.json` pokazuje od razu, w którym pliku nazwa jest zdefiniowana, a mapa
    paczki z dziesiątkami tysięcy symboli ma kilka megabajtów, nie kilkanaście.

    Example args:
        symbol_map=SymbolMap(built_on="2026-10-13", files={"src/a.php": [Symbol(…)]})

    Example result:
        '{\\n"built_on": "2026-10-13",\\n"syntax_errors": [],\\n"files": {\\n'
        '"src/a.php": [{"name": "A", "scope": null, "kind": "class", …}]\\n}\\n}\\n'
    """
    files = [
        f"{json.dumps(path, ensure_ascii=False)}: "
        f"{json.dumps([dataclasses.asdict(symbol) for symbol in symbols], ensure_ascii=False)}"
        for path, symbols in symbol_map.files.items()
    ]
    lines = [
        "{",
        f'"built_on": {json.dumps(symbol_map.built_on)},',
        f'"syntax_errors": {json.dumps(symbol_map.syntax_errors, ensure_ascii=False)},',
        '"files": {',
        ",\n".join(files),
        "}",
        "}",
    ]

    return "\n".join(lines) + "\n"


def build_symbols(
    package_dir: pathlib.Path,  # np. Path("data/unsafe/code")
) -> SymbolMap:
    """
    Description:
    Buduje mapę symboli paczki: rozbiera każdy plik PHP i JS z `repo/` i zapisuje wynik do
    `symbols.json` w katalogu paczki. Poprzednią mapę kasuje na początku.

    Example args:
        package_dir=Path("data/unsafe/code")

    Example result:
        SymbolMap(built_on="2026-10-13", files={"src/…/GeneratorNumeru.php": [Symbol(…), …]},
                  syntax_errors=[])

    Raises:
        ValueError: w katalogu nie ma `repo/`, czyli paczki nie zbudowano
    """
    code_dir     = package_dir / CODE_DIR
    symbols_path = package_dir / SYMBOLS_NAME
    if not code_dir.is_dir():
        raise ValueError(f"Nie ma paczki: {code_dir} nie jest katalogiem.")

    # --- stara mapa znika pierwsza: przerwany przebieg ma zostawić brak mapy, nie mapę ---
    # --- poprzedniego kodu ---
    symbols_path.unlink(missing_ok=True)

    symbol_map = SymbolMap(built_on=datetime.date.today().isoformat())
    for file in sorted(code_dir.rglob("*")):
        path = file.relative_to(code_dir).as_posix()
        if not file.is_file() or language_of(path) is None:
            continue

        symbols = symbols_of_file(path, file.read_bytes())
        # --- błąd składni: plik bez symboli, ale widoczny na liście ---
        if symbols is None:
            symbol_map.syntax_errors.append(path)
        # --- plik bez definicji (szablon, konfiguracja w PHP) nie dostaje pustego wpisu ---
        elif symbols:
            symbol_map.files[path] = symbols

    symbols_path.write_text(symbols_as_json(symbol_map), encoding="utf-8")

    return symbol_map


def report_symbols(
    symbol_map:  SymbolMap,
    package_dir: pathlib.Path,  # np. Path("data/unsafe/code")
) -> None:
    """
    Description:
    Wypisuje podsumowanie mapy: ile symboli w ilu plikach i które pliki parser odrzucił.

    Example args:
        symbol_map=SymbolMap(built_on="2026-10-13", files={…}, syntax_errors=[])
        package_dir=Path("data/unsafe/code")

    Example result:
        None (linie na stdout)
    """
    total = sum(len(symbols) for symbols in symbol_map.files.values())
    typer.echo(f"Mapa symboli: {total} symboli w {len(symbol_map.files)} plikach, "
               f"zapisana w {package_dir / SYMBOLS_NAME}")
    # --- plik bez symboli z powodu błędu składni: model przeczyta go tylko zakresem linii ---
    for path in symbol_map.syntax_errors:
        typer.echo(f"  błąd składni, plik bez symboli: {path}")


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
HELP_COMMAND = "Buduje mapę symboli (symbols.json) dla zbudowanej paczki kodu."
HELP_PACKAGE = "Katalog zbudowanej paczki: repo/ z kodem, a obok manifest.json."


@cli.command(help=HELP_COMMAND)
def build(
    package_dir: pathlib.Path = typer.Argument(..., help=HELP_PACKAGE),
) -> None:
    """
    Description:
    Buduje mapę symboli paczki i wypisuje podsumowanie.

    Example args:
        package_dir=Path("data/unsafe/code")

    Example result:
        None (mapa na dysku + podsumowanie na stdout)

    Raises:
        typer.Exit: gdy w katalogu nie ma zbudowanej paczki
    """
    try:
        symbol_map = build_symbols(package_dir)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    report_symbols(symbol_map, package_dir)


if __name__ == "__main__":
    cli()
