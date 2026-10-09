from app.engine_process.ripgrep.client import parse_ripgrep_output

# Wyjście ripgrepa w kształcie, o który prosi klient: ścieżka, znak zerowy, numer linii, dwukropek
# i treść. Test nie uruchamia programu — sprawdza sam rozbiór tekstu.


def _row(
    path:    str,  # np. "./src/lib/Blad.php"
    number:  int,  # np. 18
    content: str,  # np. "    throw new Blad('Brak sekwencji');"
) -> str:
    """
    Description:
    Składa jedną linię wyjścia ripgrepa.

    Example args:
        path="./src/lib/Blad.php"
        number=18
        content="    throw new Blad('Brak sekwencji');"

    Example result:
        "./src/lib/Blad.php\\x0018:    throw new Blad('Brak sekwencji');\\n"
    """
    return f"{path}\0{number}:{content}\n"


def test_a_row_becomes_a_line_with_path_number_and_text() -> None:
    """Sprawdza, czy z linii wyjścia ripgrepa powstaje trafienie ze ścieżką bez początkowego `./`,
    numerem linii jako liczbą i treścią razem z wcięciem.

    Wyłapuje ścieżkę oddawaną z `./`, którą ripgrep dokleja przy szukaniu w całym katalogu: ta
    sama linia miałaby inną ścieżkę przy szukaniu w całości i w podkatalogu, a narzędzie cytujące
    dostawałoby dwa zapisy jednego pliku."""
    [line] = parse_ripgrep_output(_row("./src/lib/Blad.php", 18, "    throw new Blad('Brak');"))

    assert (line.path, line.line) == ("src/lib/Blad.php", 18)
    assert line.text              == "    throw new Blad('Brak');"


def test_colons_in_the_code_and_in_the_file_name_do_not_break_a_row() -> None:
    """Sprawdza, czy linia kodu z dwukropkami i plik z dwukropkiem w nazwie wracają w całości:
    ścieżkę od reszty oddziela znak zerowy, a numer od treści pierwszy dwukropek po nim.

    Wyłapuje rozbiór po pierwszym dwukropku w linii: nazwa pliku zostałaby ucięta, a kawałek
    ścieżki trafiłby do numeru linii albo do treści."""
    [line] = parse_ripgrep_output(_row("src/a:b.php", 7, "return $a ? 'x: y' : 'z';"))

    assert (line.path, line.line) == ("src/a:b.php", 7)
    assert line.text              == "return $a ? 'x: y' : 'z';"


def test_lines_are_ordered_by_path_and_then_by_line_number() -> None:
    """Sprawdza, czy trafienia podane w przypadkowej kolejności wracają ułożone po ścieżce,
    a w jednym pliku po numerze linii liczonym jak liczba: linia 2 stoi przed linią 10.

    Wyłapuje wynik w kolejności, w jakiej ripgrep akurat oddał pliki: zmienia się ona między
    przebiegami, więc limit wyniku ucinałby za każdym razem inne linie. Wyłapuje też porównanie
    numerów jak napisów, przy którym linia 10 wyprzedza linię 2."""
    output = (
        _row("src/b.php", 10, "b dziesięć")
        + _row("src/a.php", 3, "a trzy")
        + _row("src/b.php", 2, "b dwa")
    )

    found = parse_ripgrep_output(output)

    assert [(line.path, line.line) for line in found] == [
        ("src/a.php", 3),
        ("src/b.php", 2),
        ("src/b.php", 10),
    ]


def test_empty_output_gives_no_lines() -> None:
    """Sprawdza, czy z pustego wyjścia ripgrepa powstaje pusta lista trafień.

    Wyłapuje rozbiór, który na pustym tekście kończy się wyjątkiem albo oddaje trafienie bez
    ścieżki: brak trafień to zwykły wynik szukania."""
    assert parse_ripgrep_output("") == []
