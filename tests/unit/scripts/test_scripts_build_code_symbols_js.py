"""
Description:
Testy jednostkowe wybierania definicji z pliku JS (`symbols_of_file` ze
`scripts/build_code_symbols.py`). W JS funkcja rzadko jest deklaracją: zwykle to przypisanie do
ścieżki nazw albo pole obiektu, więc większość testów pilnuje nazwy i tego, w czym definicja
leży (`scope`). Źródła są zmyślone. Rozbiór PHP ma własny plik testów.
"""

import textwrap

from build_code_symbols import symbols_of_file


def _symbols(
    source: str,  # treść pliku JS, wcięta jak kod testu
) -> list[tuple[str, str | None, str, int, int]] | None:
    """
    Description:
    Rozbiera zmyślony plik JS i oddaje jego symbole jako krotki: nazwa, w czym leży, rodzaj,
    pierwsza i ostatnia linia. Wcięcie wspólne dla całego źródła jest zdejmowane.

    Example args:
        source="function odswiez() {\\n}\\n"

    Example result:
        [("odswiez", None, "function", 1, 2)]
    """
    symbols = symbols_of_file("plik.js", textwrap.dedent(source).encode("utf-8"))
    if symbols is None:
        return None

    return [(s.name, s.scope, s.kind, s.from_line, s.to_line) for s in symbols]


def test_a_declaration_and_a_function_assigned_to_a_variable_are_symbols() -> None:
    """Sprawdza, czy deklaracja `function`, funkcja przypisana do zmiennej i funkcja
    strzałkowa przypisana do stałej dają po jednym wpisie, bez nazwy miejsca.

    Wyłapuje rozbiór znający tylko deklaracje: funkcje zapisane przypisaniem, czyli większość
    kodu JS aplikacji, nie trafiłyby do mapy."""
    source = """\
        function odswiez(lista) {
            lista.reload();
        }

        var policz = function (wiersze) {
            return wiersze.length;
        };
        const podwoj = (liczba) => liczba * 2;
        """

    assert _symbols(source) == [
        ("odswiez", None, "function", 1, 3),
        ("policz",  None, "function", 5, 7),
        ("podwoj",  None, "function", 8, 8),
    ]


def test_a_function_assigned_to_a_dotted_path_is_named_by_its_last_part() -> None:
    """Sprawdza, czy funkcja przypisana do ścieżki z kropkami dostaje jako nazwę ostatni człon
    ścieżki, a resztę jako miejsce — także gdy ścieżka prowadzi przez `prototype`.

    Wyłapuje nazwę zapisaną razem ze ścieżką: ta sama funkcja nazywałaby się inaczej niż
    w wywołaniu `obsluzBlad(…)`, a pole obiektu i przypisanie dawałyby dwa różne kształty
    nazwy tej samej rzeczy."""
    source = """\
        OBI.sprawy.obsluzBlad = function (odpowiedz) {
            alert(odpowiedz.msg);
        };
        OBI.Lista.prototype.rysuj = function () {
        };
        """

    assert _symbols(source) == [
        ("obsluzBlad", "OBI.sprawy",          "function", 1, 3),
        ("rysuj",      "OBI.Lista.prototype", "function", 4, 5),
    ]


def test_functions_in_an_object_take_the_name_the_object_is_assigned_to() -> None:
    """Sprawdza, czy funkcje zapisane jako pola obiektu — zwykłe, strzałkowe, skrótem i pod
    kluczem w cudzysłowie — dostają jako miejsce ścieżkę, do której obiekt przypisano.

    Wyłapuje pola obiektu bez miejsca: handler `zapisz` z modułu pism i handler `zapisz`
    z modułu spraw różniłyby się wtedy tylko plikiem."""
    source = """\
        APP.pisma = {
            zapisz: function (parametry) {
                return parametry.id;
            },
            wyslij: (parametry) => parametry.id,
            anuluj() {
            },
            'Zamknij okno': function () {
            }
        };
        """

    assert _symbols(source) == [
        ("zapisz",       "APP.pisma", "function", 2, 4),
        ("wyslij",       "APP.pisma", "function", 5, 5),
        ("anuluj",       "APP.pisma", "function", 6, 7),
        ("Zamknij okno", "APP.pisma", "function", 8, 9),
    ]


def test_a_nested_object_extends_the_place_by_its_key() -> None:
    """Sprawdza, czy funkcja w obiekcie zagnieżdżonym w innym obiekcie dostaje jako miejsce
    ścieżkę przedłużoną o klucz, pod którym obiekt wewnętrzny leży, a obiekt zadeklarowany
    zmienną — nazwę zmiennej.

    Wyłapuje miejsce urwane na obiekcie zewnętrznym: dwie funkcje `zapisz` z dwóch grup
    przycisków jednego okna miałyby tę samą nazwę i to samo miejsce."""
    source = """\
        APP.okna = {
            przyciski: {
                zapisz: function () {
                }
            }
        };
        var Narzedzia = {
            przytnij: function (tekst) {
                return tekst.trim();
            }
        };
        """

    assert _symbols(source) == [
        ("zapisz",   "APP.okna.przyciski", "function", 3, 4),
        ("przytnij", "Narzedzia",          "function", 8, 10),
    ]


def test_a_function_inside_another_function_is_not_a_symbol() -> None:
    """Sprawdza, czy funkcje podane jako argument albo przypisane wewnątrz innej funkcji nie
    dostają własnych wpisów: plik daje jedną funkcję, która kończy się za nimi.

    Wyłapuje schodzenie w ciało funkcji: plik aplikacji miałby dziesiątki wpisów `success`
    i `click`, a odczyt handlera kończyłby się przed jego funkcją zwrotną."""
    source = """\
        APP.sprawy.zapisz = function (parametry) {
            var formatuj = function (wynik) {
                return wynik.numer;
            };
            $.ajax({
                url: '/sprawy/zapisz',
                success: function (wynik) {
                    $('#numer').text(formatuj(wynik));
                },
                error: function () {
                }
            });
        };
        """

    assert _symbols(source) == [("zapisz", "APP.sprawy", "function", 1, 13)]


def test_nothing_inside_a_field_a_method_or_a_declaration_is_a_symbol() -> None:
    """Sprawdza to samo dla pozostałych zapisów funkcji: pole obiektu, metoda klasy
    i deklaracja `function` z funkcjami w środku dają po jednym wpisie, bez wpisów dla
    funkcji wewnętrznych.

    Wyłapuje regułę „w ciało funkcji nie schodzimy" pilnowaną tylko dla jednego zapisu:
    handlery aplikacji to głównie pola obiektów, więc mapa wypełniłaby się ich funkcjami
    zwrotnymi."""
    source = """\
        APP.pisma = {
            wyslij: function (parametry) {
                $.ajax({
                    success: function (wynik) {
                    }
                });
            }
        };
        class Kolejka {
            uruchom() {
                var krok = function () {
                };
            }
        }
        function odswiez() {
            function pomocnik() {
            }
        }
        """

    assert _symbols(source) == [
        ("wyslij",  "APP.pisma", "function", 2, 7),
        ("Kolejka", None,        "class",    9, 14),
        ("uruchom", "Kolejka",   "method",   10, 13),
        ("odswiez", None,        "function", 15, 18),
    ]


def test_definitions_inside_a_nameless_wrapper_are_symbols() -> None:
    """Sprawdza, czy funkcje zdefiniowane w funkcji bez nazwy, która opakowuje cały plik, są
    w mapie — tak jak funkcja w obiekcie zwracanym z takiego opakowania.

    Wyłapuje traktowanie opakowania jak zwykłej funkcji: plik pisany w ten sposób nie miałby
    w mapie ani jednej funkcji."""
    source = """\
        $(function () {
            function odswiez() {
            }
            var policz = function () {
            };
        });
        APP.kalendarz = (function () {
            return {
                pokaz: function () {
                }
            };
        })();
        """

    assert _symbols(source) == [
        ("odswiez", None, "function", 2, 3),
        ("policz",  None, "function", 4, 5),
        ("pokaz",   None, "function", 9, 10),
    ]


def test_a_function_in_an_object_passed_to_a_call_has_no_place() -> None:
    """Sprawdza, czy funkcja w obiekcie podanym wprost jako argument wywołania trafia do mapy
    bez miejsca, a obiekt w tablicy nie dziedziczy miejsca po obiekcie, w którym tablica leży.

    Wyłapuje miejsce przenoszone przez wywołanie albo tablicę: kolumny siatki dałyby
    kilkanaście funkcji o tej samej nazwie i tym samym miejscu."""
    source = """\
        $('#lista').jqGrid({
            onSelectRow: function (id) {
            }
        });
        APP.siatka = {
            kolumny: [
                { dataInit: function (pole) {
                } },
                { dataInit: function (pole) {
                } }
            ]
        };
        """

    assert _symbols(source) == [
        ("onSelectRow", None, "function", 2, 3),
        ("dataInit",    None, "function", 7, 8),
        ("dataInit",    None, "function", 9, 10),
    ]


def test_a_class_and_its_methods_are_symbols() -> None:
    """Sprawdza, czy klasa JS daje wpis klasy, a jej metody wpisy z nazwą klasy jako miejscem.

    Wyłapuje metody klasy bez miejsca albo oznaczone jak zwykłe funkcje: konstruktora jednej
    klasy nie dałoby się odróżnić od konstruktora drugiej w tym samym pliku."""
    source = """\
        class Kolejka {
            constructor(limit) {
                this.limit = limit;
            }
            dodaj(wpis) {
            }
        }
        """

    assert _symbols(source) == [
        ("Kolejka",     None,      "class",  1, 7),
        ("constructor", "Kolejka", "method", 2, 4),
        ("dodaj",       "Kolejka", "method", 5, 6),
    ]


def test_a_target_that_is_not_a_plain_path_gives_no_place_or_no_symbol() -> None:
    """Sprawdza, czy funkcja przypisana do pola wyniku wywołania trafia do mapy bez miejsca,
    a funkcja przypisana do elementu tablicy albo pod klucz wyliczany nie trafia wcale.

    Wyłapuje nazwy i miejsca sklejane z dowolnego wyrażenia: w mapie stałyby fragmenty kodu
    z nawiasami zamiast nazw, pod którymi nikt funkcji nie szuka."""
    source = """\
        $(this).data('okno').zamknij = function () {
        };
        obsluga[0] = function () {
        };
        APP.akcje = {
            [nazwaAkcji]: function () {
            }
        };
        """

    assert _symbols(source) == [("zamknij", None, "function", 1, 2)]


def test_braces_in_strings_templates_and_regexes_do_not_end_a_function_early() -> None:
    """Sprawdza, czy nawias klamrowy w napisie, w szablonie tekstu, w wyrażeniu regularnym
    i w komentarzu nie kończy funkcji: jej ostatnia linia to prawdziwy nawias zamykający.

    Wyłapuje wyznaczanie końca funkcji liczeniem nawiasów w tekście: funkcja składająca
    komunikat byłaby ucięta w połowie."""
    source = """\
        function komunikat(pismo) {
            var zamkniecie = '}';   // } to nie koniec funkcji
            var wzorzec = /\\}+/;
            return `Pismo ${pismo.numer} }`;
        }
        function nastepna() {
        }
        """

    assert _symbols(source) == [
        ("komunikat", None, "function", 1, 5),
        ("nastepna",  None, "function", 6, 7),
    ]


def test_a_file_with_a_syntax_error_gives_no_symbols_at_all() -> None:
    """Sprawdza, czy plik JS z błędem składni nie daje żadnego symbolu, także z poprawnej
    funkcji obok: wynikiem jest brak wyniku.

    Wyłapuje branie symboli z pliku, którego parser nie rozebrał: granice funkcji po błędzie
    bywają przesunięte."""
    source = """\
        function dobra() {
        }
        function zla( {
        }
        """

    assert _symbols(source) is None
