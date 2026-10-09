"""
Description:
Testy integracyjne klienta ripgrepa (`RipgrepClient`) na prawdziwym programie `rg` i małych
drzewach plików w katalogu tymczasowym. Bez stacku; wymagają ripgrepa na hoście
(`apt install ripgrep`) — jego brak kończy testy błędem, nie pominięciem.

| co sprawdzamy                | przykłady                                                  |
|------------------------------|------------------------------------------------------------|
| fraza to tekst               | wielkość liter, myślnik na początku, znaki wyrażeń         |
| słowa                        | dowolna kolejność, komplet, nie w nazwie pliku             |
| kolejność i ścieżki          | po ścieżce i numerze linii, zawężenie do katalogu i pliku  |
| niezależność od maszyny      | pliki `.ignore` i pliki ukryte nie chowają kodu            |
| awarie                       | brak programu, błąd programu, limit czasu                  |
"""

from pathlib import Path

import pytest

from app.engine_process import ProcessConfigError, ProcessError
from app.engine_process.ripgrep import RipgrepClient
from app.engine_process.ripgrep import client as ripgrep_client

BLEDY = "src/web/js/bledy.js"
KLIENT = "src/lib/Http/KlientUslugi.php"

FILES = {
    BLEDY: "\n".join([
        "function pokazBlad(tresc) {",
        "    okno('Nie udało się skomunikować z serwerem');",
        "}",
    ]) + "\n",
    KLIENT: "\n".join([
        "<?php",
        "class KlientUslugi",
        "{",
        "    throw new Blad('Z serwerem usługi nie udało się skomunikować: ' . $this->adres);",
        "}",
    ]) + "\n",
}


def _tree(
    tmp_path: Path,                   # katalog tymczasowy testu
    files:    dict[str, str] = FILES, # np. {"src/a.php": "<?php\n"}
) -> Path:
    """
    Description:
    Zakłada katalog z podanymi plikami, czyli to, w czym klient ma szukać.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        files={"src/a.php": "<?php\\n"}

    Example result:
        Path("/tmp/pytest-of-root/pytest-0/test_x0/kod")
    """
    root = tmp_path / "kod"

    for path, content in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(content, encoding="utf-8")

    return root


def _client() -> RipgrepClient:
    """
    Description:
    Klient z limitem czasu, w którym szukanie w kilku plikach mieści się z dużym zapasem.

    Example args:
        (brak)

    Example result:
        RipgrepClient, którego szukanie trwa najwyżej 10 s
    """
    return RipgrepClient(timeout=10.0)


async def test_a_phrase_is_found_whatever_the_case(tmp_path: Path) -> None:
    """Sprawdza, czy fraza zapisana wielkimi literami, także z polskimi znakami, znajduje linię,
    w której stoi małymi, i czy trafienie niesie ścieżkę względem katalogu, numer linii i całą
    treść razem z wcięciem.

    Wyłapuje szukanie rozróżniające wielkość liter albo takie, które nie zrównuje „Ć" z „ć":
    komunikat przepisany z ekranu inaczej, niż stoi w kodzie, przestałby się znajdować."""
    [line] = await _client().find_substring(_tree(tmp_path), "NIE UDAŁO SIĘ SKOMUNIKOWAĆ Z")

    assert (line.path, line.line) == (BLEDY, 2)
    assert line.text              == "    okno('Nie udało się skomunikować z serwerem');"


async def test_a_phrase_is_text_not_a_pattern_nor_a_flag(tmp_path: Path) -> None:
    """Sprawdza, czy fraza ze znakami wyrażeń regularnych znajduje tylko linię, w której stoi
    dosłownie, a fraza zaczynająca się od myślnika jest szukana jak każda inna.

    Wyłapuje frazę podaną ripgrepowi jako wzorzec: „.*" pasowałoby do wszystkiego. Wyłapuje też
    frazę wziętą za flagę programu: kod błędu z myślnikiem kończyłby szukanie błędem."""
    root = _tree(tmp_path, {
        "src/a.php": "$wzorzec = 'adres.*';\n$inny = 'adresXYZ';\n$kod = 'ORA-00942';\n",
    })

    pattern = await _client().find_substring(root, "adres.*")
    dashed  = await _client().find_substring(root, "-00942")

    assert [line.line for line in pattern] == [1]
    assert [line.line for line in dashed]  == [3]


async def test_whitespace_in_a_phrase_counts_as_one_space(tmp_path: Path) -> None:
    """Sprawdza, czy fraza przełamana znakiem nowej linii i rozdzielona kilkoma spacjami
    znajduje linię, w której te słowa dzieli jedna spacja, a fraza z samych białych znaków nie
    znajduje niczego.

    Wyłapuje frazę podaną ripgrepowi razem ze znakiem nowej linii, co kończy szukanie błędem:
    komunikat przeklejony ze zgłoszenia bywa złamany w połowie. Wyłapuje też pustą frazę, która
    pasowałaby do każdej linii każdego pliku."""
    root = _tree(tmp_path)

    broken = await _client().find_substring(root, "Nie udało\nsię   skomunikować")
    blank  = await _client().find_substring(root, " \n\t ")

    assert [(line.path, line.line) for line in broken] == [(KLIENT, 4), (BLEDY, 2)]
    assert blank                                       == []


async def test_words_may_come_in_any_order_but_all_are_required(tmp_path: Path) -> None:
    """Sprawdza, czy szukanie słowami znajduje linie zawierające wszystkie słowa bez względu na
    ich kolejność i wielkość liter, a słowo, którego w linii nie ma, wyklucza ją z wyniku.

    Wyłapuje szukanie słowami, które wymaga kolejności, czyli nie znajduje komunikatu o innym
    szyku, oraz takie, któremu wystarcza jedno słowo, czyli zalewa wynik przypadkowymi liniami."""
    root = _tree(tmp_path)

    both_files = await _client().find_words(root, "SERWEREM skomunikować")
    one_file   = await _client().find_words(root, "skomunikować serwerem usługi")

    assert [(line.path, line.line) for line in both_files] == [(KLIENT, 4), (BLEDY, 2)]
    assert [(line.path, line.line) for line in one_file]   == [(KLIENT, 4)]


async def test_a_word_in_the_file_name_does_not_count(tmp_path: Path) -> None:
    """Sprawdza, czy linia nie jest uznawana za zawierającą słowo, które stoi tylko w nazwie jej
    pliku: plik `serwer.js` z linią o zerwanym połączeniu nie pasuje do słów „zerwane serwer".

    Wyłapuje sprawdzanie słów na linii wyjścia ripgrepa, w której przed treścią stoi ścieżka:
    słowo „js" pasowałoby wtedy do każdej linii każdego pliku `.js`."""
    root = _tree(tmp_path, {"src/web/js/serwer.js": "komunikat('połączenie zerwane');\n"})

    found = await _client().find_words(root, "zerwane serwer")

    assert found == []


async def test_lines_come_ordered_by_path_and_line_number(tmp_path: Path) -> None:
    """Sprawdza, czy trafienia z kilku plików wracają ułożone po ścieżce, a w jednym pliku po
    numerze linii, także gdy linia 10 i linia 2 pasują obie.

    Wyłapuje wynik w kolejności, w jakiej ripgrep akurat przeszukał pliki: zmienia się ona
    między przebiegami, więc limit narzędzia ucinałby za każdym razem inne linie."""
    filler = "\n".join(["// nic"] * 7)
    root   = _tree(tmp_path, {
        "src/b.php": f"<?php\ntrafienie();\n{filler}\ntrafienie();\n",
        "src/a.php": "<?php\n\ntrafienie();\n",
    })

    found = await _client().find_substring(root, "trafienie")

    assert [(line.path, line.line) for line in found] == [
        ("src/a.php", 3),
        ("src/b.php", 2),
        ("src/b.php", 10),
    ]


async def test_a_search_can_be_narrowed_to_a_directory_or_a_file(tmp_path: Path) -> None:
    """Sprawdza, czy szukanie zawężone do katalogu i do pojedynczego pliku oddaje tylko trafienia
    stamtąd, ze ścieżką w tym samym kształcie co przy szukaniu w całości: względną wobec
    katalogu głównego.

    Wyłapuje zawężenie, które zmienia kształt ścieżki (samą nazwę pliku albo ścieżkę od
    zawężonego katalogu): model nie mógłby podać takiej ścieżki narzędziu cytującemu."""
    root = _tree(tmp_path)

    in_directory = await _client().find_substring(root, "skomunikować", "src/lib")
    in_file      = await _client().find_substring(root, "skomunikować", BLEDY)

    assert [line.path for line in in_directory] == [KLIENT]
    assert [line.path for line in in_file]      == [BLEDY]


async def test_a_text_that_is_nowhere_gives_no_lines(tmp_path: Path) -> None:
    """Sprawdza, czy szukanie tekstu, którego nie ma w żadnym pliku, oddaje pustą listę, frazą
    i słowami.

    Wyłapuje brak trafień zgłaszany jako błąd programu: ripgrep kończy wtedy kodem 1, a „takiego
    tekstu nie ma w kodzie" to częsta i poprawna odpowiedź."""
    root = _tree(tmp_path)

    assert await _client().find_substring(root, "TWAIN")          == []
    assert await _client().find_words(root, "skaner sterownik")   == []


async def test_ignore_files_and_hidden_files_do_not_hide_code(tmp_path: Path) -> None:
    """Sprawdza, czy szukanie znajduje tekst w pliku wymienionym w `.ignore` i w pliku, którego
    nazwa zaczyna się od kropki.

    Wyłapuje szukanie z domyślnymi regułami ripgrepa, który takie pliki pomija: model mógłby
    odczytać plik, którego szukanie nie widzi, a wynik zależałby od plików leżących obok kodu."""
    root = _tree(tmp_path, {
        ".ignore":            "pominiety.php\n",
        "src/pominiety.php":  "<?php trafienie();\n",
        "src/.ukryty.php":    "<?php trafienie();\n",
    })

    found = await _client().find_substring(root, "trafienie")

    assert [line.path for line in found] == ["src/.ukryty.php", "src/pominiety.php"]


async def test_the_last_line_without_a_newline_keeps_its_number(tmp_path: Path) -> None:
    """Sprawdza, czy trafienie w ostatniej linii pliku, który nie kończy się znakiem nowej linii,
    ma numer tej linii: trzecia linia pliku to linia 3.

    Wyłapuje numerację przesuniętą o jeden na końcu pliku: numer z szukania nie zgadzałby się
    z numerem, którego oczekuje narzędzie cytujące."""
    root = _tree(tmp_path, {"src/a.php": "<?php\n\ntrafienie();"})

    [line] = await _client().find_substring(root, "trafienie")

    assert line.line == 3


async def test_a_missing_ripgrep_is_a_configuration_error(
    tmp_path:    Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy szukanie przy braku programu ripgrep w systemie kończy się wyjątkiem
    `ProcessConfigError`. Test podmienia nazwę programu na taką, której nie ma.

    Wyłapuje brak ripgrepa oddawany jako „nic nie znaleziono": obraz zbudowany bez programu
    odpowiadałby tak na każde pytanie o kod i nikt by tego nie zauważył."""
    monkeypatch.setattr(ripgrep_client, "RIPGREP", "nie-ma-takiego-rg")

    with pytest.raises(ProcessConfigError, match="nie-ma-takiego-rg"):
        await _client().find_substring(_tree(tmp_path), "skomunikować")


async def test_a_search_ripgrep_could_not_finish_is_an_error(tmp_path: Path) -> None:
    """Sprawdza, czy szukanie w ścieżce, której nie ma, kończy się wyjątkiem `ProcessError`:
    ripgrep zgłasza wtedy błąd kodem wyjścia 2.

    Wyłapuje błąd programu wzięty za brak trafień: wołający dostałby pustą listę i uznał, że
    tekstu nie ma w kodzie, choć szukanie się nie odbyło."""
    with pytest.raises(ProcessError):
        await _client().find_substring(_tree(tmp_path), "skomunikować", "src/nie-ma")


async def test_a_search_over_the_time_limit_is_an_error(
    tmp_path:    Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy szukanie, które nie kończy się w limicie czasu klienta, kończy się wyjątkiem
    `ProcessError` niebędącym błędem konfiguracji. Test podmienia ripgrepa na skrypt, który
    czeka 5 sekund, a klientowi daje limit 0,2 sekundy.

    Wyłapuje klienta, który nie przekazuje swojego limitu czasu do uruchamiania programu:
    szukanie na wolnym dysku wstrzymywałoby żądanie bez końca."""
    slow = tmp_path / "wolny-rg"
    slow.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    slow.chmod(0o755)
    monkeypatch.setattr(ripgrep_client, "RIPGREP", str(slow))

    with pytest.raises(ProcessError) as caught:
        await RipgrepClient(timeout=0.2).find_substring(_tree(tmp_path), "skomunikować")

    assert not isinstance(caught.value, ProcessConfigError)
