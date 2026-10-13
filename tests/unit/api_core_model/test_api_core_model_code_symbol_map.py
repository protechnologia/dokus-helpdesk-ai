from datetime import date

import pytest
from pydantic import ValidationError

from app.core_model.code.code_symbol_map import CodeSymbolMap

# Mapa w kształcie pliku `symbols.json`: jeden plik z jedną funkcją i jeden plik odrzucony.
MAP = {
    "built_on":      "2026-10-13",
    "syntax_errors": ["src/lib/zepsuty.php"],
    "files":         {
        "src/web/js/okna.js": [
            {"name": "zamknij", "scope": "APP.okna", "kind": "function",
             "from_line": 2, "to_line": 3},
        ],
    },
}


def test_a_map_keeps_its_files_symbols_and_rejected_files() -> None:
    """Sprawdza, czy mapa w kształcie pliku `symbols.json` staje się modelem: dzień budowy jest
    datą, symbole pliku są modelami symboli, a lista plików odrzuconych zostaje bez zmian.

    Wyłapuje model, który nie zamienia wpisów na symbole: narzędzie dostawałoby słowniki
    i sięgało po pola, których nikt nie sprawdził."""
    symbol_map = CodeSymbolMap.model_validate(MAP)

    assert symbol_map.built_on == date(2026, 10, 13)
    assert symbol_map.syntax_errors == ["src/lib/zepsuty.php"]
    assert symbol_map.files["src/web/js/okna.js"][0].name == "zamknij"


@pytest.mark.parametrize(
    "changed",
    [
        {"built_on": "wczoraj"},
        {"syntax_errors": None},
        {"files": [["src/web/js/okna.js"]]},
        {"files": {"src/web/js/okna.js": [{"name": "zamknij"}]}},
        {"package": "data/unsafe/code"},
    ],
    ids=["zła data", "bez odrzuconych", "pliki jako lista", "niepełny symbol", "nieznane pole"],
)
def test_a_map_of_another_shape_is_refused(changed: dict) -> None:
    """Sprawdza, czy mapa ze złą datą, bez listy plików odrzuconych, z plikami zapisanymi jako
    lista, z niepełnym wpisem symbolu albo z polem spoza modelu kończy się wyjątkiem
    `ValidationError`.

    Wyłapuje model, który przyjmuje plik o innym kształcie: mapa zapisana starszą wersją
    skryptu byłaby czytana do połowy, bez żadnego błędu."""
    with pytest.raises(ValidationError):
        CodeSymbolMap.model_validate({**MAP, **changed})


@pytest.mark.parametrize("missing", ["built_on", "syntax_errors", "files"])
def test_every_part_of_the_map_is_required(missing: str) -> None:
    """Sprawdza, czy mapa bez dnia budowy, bez listy plików odrzuconych albo bez listy plików
    kończy się wyjątkiem `ValidationError`.

    Wyłapuje pole z wartością domyślną: mapa bez listy plików wyglądałaby wtedy jak paczka,
    w której nie ma ani jednej funkcji."""
    with pytest.raises(ValidationError):
        CodeSymbolMap.model_validate({key: value for key, value in MAP.items() if key != missing})
