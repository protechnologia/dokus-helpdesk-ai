"""
Description:
Testy jednostkowe wybierania definicji z pliku PHP (`symbols_of_file` ze
`scripts/build_code_symbols.py`): klasy, interfejsy, traity, metody i funkcje, każda z pierwszą
i ostatnią linią. Źródła są zmyślone i krótkie, więc numery linii w asercjach da się policzyć
w głowie. Budowę całej mapy z paczki sprawdzają testy integracyjne.
"""

import textwrap

from build_code_symbols import symbols_of_file


def _symbols(
    source: str,  # treść pliku PHP, wcięta jak kod testu
) -> list[tuple[str, str | None, str, int, int]] | None:
    """
    Description:
    Rozbiera zmyślony plik PHP i oddaje jego symbole jako krotki: nazwa, w czym leży, rodzaj,
    pierwsza i ostatnia linia. Wcięcie wspólne dla całego źródła jest zdejmowane, więc `<?php`
    stoi w linii 1.

    Example args:
        source="<?php\\nfunction pomocnik()\\n{\\n}\\n"

    Example result:
        [("pomocnik", None, "function", 2, 4)]
    """
    symbols = symbols_of_file("plik.php", textwrap.dedent(source).encode("utf-8"))
    if symbols is None:
        return None

    return [(s.name, s.scope, s.kind, s.from_line, s.to_line) for s in symbols]


def test_a_class_and_its_methods_come_with_their_first_and_last_lines() -> None:
    """Sprawdza, czy klasa z dwiema metodami daje trzy wpisy: klasę i obie metody, każdy
    z pierwszą linią definicji i linią nawiasu zamykającego, a metody z nazwą klasy.

    Wyłapuje numery liczone od zera albo ostatnią linię bez nawiasu zamykającego: narzędzie
    oddawałoby funkcję przesuniętą o linię albo uciętą przed końcem."""
    source = """\
        <?php

        class GeneratorNumeru
        {
            private $polaczenie;

            public function nastepnyNumer($rok)
            {
                return $rok;
            }

            protected static function formatuj($numer)
            {
                return sprintf('%05d', $numer);
            }
        }
        """

    assert _symbols(source) == [
        ("GeneratorNumeru", None,              "class",  3, 16),
        ("nastepnyNumer",   "GeneratorNumeru", "method", 7, 10),
        ("formatuj",        "GeneratorNumeru", "method", 12, 15),
    ]


def test_a_method_without_a_body_takes_one_line() -> None:
    """Sprawdza, czy metoda interfejsu i metoda abstrakcyjna, które nie mają ciała, dają wpis
    kończący się w tej samej linii, w której się zaczyna.

    Wyłapuje szukanie końca metody po nawiasie klamrowym: metoda bez ciała wchłonęłaby
    następną albo cały koniec klasy."""
    source = """\
        <?php
        interface Kanal
        {
            public function wyslij($pismo);
        }
        abstract class KanalBazowy
        {
            abstract protected function adres();
            public function nazwa()
            {
                return 'kanał';
            }
        }
        """

    assert _symbols(source) == [
        ("Kanal",       None,          "interface", 2, 5),
        ("wyslij",      "Kanal",       "method",    4, 4),
        ("KanalBazowy", None,          "class",     6, 13),
        ("adres",       "KanalBazowy", "method",    8, 8),
        ("nazwa",       "KanalBazowy", "method",    9, 12),
    ]


def test_the_same_method_name_in_two_classes_of_one_file_keeps_both_scopes() -> None:
    """Sprawdza, czy dwie klasy w jednym pliku z metodą o tej samej nazwie dają dwa wpisy
    metody, każdy z nazwą swojej klasy.

    Wyłapuje nazwę klasy, która zostaje po pierwszej klasie albo ginie: dwóch metod o tej
    samej nazwie w jednym pliku nie dałoby się wtedy odróżnić."""
    source = """\
        <?php
        class Odpowiedz
        {
            public function setResponse($tresc) { $this->tresc = $tresc; }
        }
        class OdpowiedzBledu
        {
            public function setResponse($tresc) { $this->blad = $tresc; }
        }
        """

    methods = [symbol for symbol in _symbols(source) if symbol[2] == "method"]

    assert methods == [
        ("setResponse", "Odpowiedz",      "method", 4, 4),
        ("setResponse", "OdpowiedzBledu", "method", 8, 8),
    ]


def test_a_trait_and_a_function_outside_any_class_are_symbols() -> None:
    """Sprawdza, czy trait trafia do mapy pod własnym rodzajem, jego metoda z nazwą traitu,
    a funkcja poza klasą jako funkcja, która w niczym nie leży.

    Wyłapuje rozbiór znający tylko klasy: metody traitów i funkcje pomocnicze z plików bez
    klasy nie dałyby się odczytać po nazwie."""
    source = """\
        <?php
        trait Logowanie
        {
            public function zapiszLog($wpis)
            {
            }
        }

        function pomocnik($wartosc)
        {
            return trim($wartosc);
        }
        """

    assert _symbols(source) == [
        ("Logowanie", None,        "trait",    2, 7),
        ("zapiszLog", "Logowanie", "method",   4, 6),
        ("pomocnik",  None,        "function", 9, 12),
    ]


def test_braces_in_strings_comments_and_heredoc_do_not_end_a_method_early() -> None:
    """Sprawdza, czy nawias klamrowy w napisie, w komentarzu i w tekście heredoc nie kończy
    metody: jej ostatnia linia to prawdziwy nawias zamykający, a następna metoda zaczyna się
    po nim.

    Wyłapuje wyznaczanie końca metody liczeniem nawiasów w tekście: metoda z szablonem
    wiadomości w środku byłaby ucięta, a jej reszta przypisana do klasy."""
    source = """\
        <?php
        class Szablon
        {
            public function tresc($imie)
            {
                $zamkniecie = '}';   // } to nie koniec metody
                /* ani to: } */
                return <<<TXT
        Witaj {$imie}
        }
        TXT;
            }

            public function stopka()
            {
                return '--';
            }
        }
        """

    assert _symbols(source) == [
        ("Szablon", None,      "class",  2, 18),
        ("tresc",   "Szablon", "method", 4, 12),
        ("stopka",  "Szablon", "method", 14, 17),
    ]


def test_a_closure_and_an_anonymous_class_inside_a_method_are_not_symbols() -> None:
    """Sprawdza, czy funkcja bez nazwy i klasa anonimowa wewnątrz metody nie dostają własnych
    wpisów: plik daje klasę i jedną metodę, która obejmuje jedno i drugie.

    Wyłapuje schodzenie w ciało metody: metoda klasy anonimowej wyszłaby jako metoda klasy
    zewnętrznej i przesłoniłaby prawdziwą o tej samej nazwie."""
    source = """\
        <?php
        class Kolejka
        {
            public function uruchom()
            {
                $filtr = function ($wpis) {
                    return $wpis !== null;
                };
                return new class {
                    public function uruchom()
                    {
                    }
                };
            }
        }
        """

    assert _symbols(source) == [
        ("Kolejka", None,      "class",  2, 15),
        ("uruchom", "Kolejka", "method", 4, 14),
    ]


def test_a_definition_inside_a_block_or_a_template_is_found() -> None:
    """Sprawdza, czy klasa zadeklarowana wewnątrz bloku `if` i funkcja zdefiniowana w szablonie
    między znacznikami HTML trafiają do mapy z właściwymi liniami.

    Wyłapuje rozbiór, który patrzy tylko na najwyższy poziom pliku albo gubi numery linii
    w pliku mieszającym HTML z PHP: w Symfony 1 tak wygląda część klas i wszystkie szablony."""
    source = """\
        <h1>Lista pism</h1>
        <?php
        if (!class_exists('Zgodnosc')) {
            class Zgodnosc
            {
                public function wersja() { return 1; }
            }
        }
        function etykieta($pismo)
        {
            return $pismo['numer'];
        }
        ?>
        <p><?php echo etykieta($pismo) ?></p>
        """

    assert _symbols(source) == [
        ("Zgodnosc", None,       "class",    4, 7),
        ("wersja",   "Zgodnosc", "method",   6, 6),
        ("etykieta", None,       "function", 9, 12),
    ]


def test_a_file_without_definitions_gives_an_empty_list() -> None:
    """Sprawdza, czy szablon, w którym kod tylko wypisuje wartości, daje pustą listę symboli,
    a nie brak wyniku.

    Wyłapuje pomylenie pliku bez definicji z plikiem odrzuconym przez parser: szablony
    trafiałyby na listę błędów składni."""
    assert _symbols("<p><?php echo $pismo['numer'] ?></p>\n") == []


def test_a_file_with_a_syntax_error_gives_no_symbols_at_all() -> None:
    """Sprawdza, czy plik z błędem składni w jednej metodzie nie daje żadnego symbolu, także
    z poprawnej metody obok: wynikiem jest brak wyniku.

    Wyłapuje branie symboli z pliku, którego parser nie rozebrał: granice funkcji po błędzie
    bywają przesunięte, a narzędzie oddałoby je jako pewne."""
    source = """\
        <?php
        class Zepsuta
        {
            public function dobra() { return 1; }
            public function zla( { return 2; }
        }
        """

    assert _symbols(source) is None


def test_line_numbers_stay_exact_in_a_long_file() -> None:
    """Sprawdza, czy w pliku z trzystu metodami każda metoda ma dokładnie te linie, w których
    stoi, od pierwszej do ostatniej.

    Wyłapuje błąd pamięci biblioteki parsera przy odczycie wiersza węzła: w dłuższym pliku
    dawał on numery ujemne albo ten sam numer dla wielu metod, a potem kończył proces."""
    methods = [
        f"    public function akcja{number}()\n    {{\n        return {number};\n    }}\n"
        for number in range(300)
    ]
    source  = "<?php\nclass Dlugi\n{\n" + "".join(methods) + "}\n"

    # Metoda numer N zaczyna się w linii 4 + 4N i zajmuje cztery linie.
    expected = [("Dlugi", None, "class", 2, 1204)] + [
        (f"akcja{number}", "Dlugi", "method", 4 + 4 * number, 7 + 4 * number)
        for number in range(300)
    ]

    assert _symbols(source) == expected


def test_a_class_stands_before_a_method_that_starts_in_the_same_line() -> None:
    """Sprawdza, czy klasa, której pierwsza metoda zaczyna się w tej samej linii co klasa, stoi
    na liście symboli przed tą metodą.

    Wyłapuje kolejność zależną od przypadku: lista symboli pliku ma stać w kolejności kodu,
    z klasą przed jej metodami, także gdy zaczynają się w tej samej linii."""
    source = """\
        <?php
        class BrakSekwencji extends Exception { public function kod() {
                return 17;
            }
        }
        """

    assert _symbols(source) == [
        ("BrakSekwencji", None,            "class",  2, 5),
        ("kod",           "BrakSekwencji", "method", 2, 4),
    ]
