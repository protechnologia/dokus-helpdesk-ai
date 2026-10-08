"""
Description:
Testy jednostkowe doboru plików do paczki kodu (`scripts/build_code_package.py`): `is_taken`
rozstrzyga o jednej ścieżce na podstawie reguł, bez dotykania dysku.

| reguła                    | czego pilnują testy                                            |
|---------------------------|----------------------------------------------------------------|
| `extensions` + `folders`  | plik wchodzi tylko z rozszerzeniem z listy, w folderze z listy |
| `files`                   | plik wskazany wprost wchodzi; gwiazdka w jednym katalogu       |
| `excluded_folders`        | nazwa działa na każdej głębokości, ścieżka w jednym miejscu    |
| `excluded_files`          | nazwa pliku działa w dowolnym katalogu                         |
| wyłączenia razem          | wygrywają z `files` i nie rozróżniają wielkości liter          |

Reguły mają kształt reguł aplikacji syntetycznej (`data/safe/code/rules.json`), ale są wpisane
tutaj: test jednostkowy nie czyta plików. Budowę paczki z tej aplikacji sprawdza test
integracyjny.
"""

import dataclasses

import pytest
from build_code_package import Rules, is_listed_file, is_taken

RULES = Rules(
    extensions       = ("php", "js", "twig"),
    folders          = ("src/apps", "src/lib", "src/web/js"),
    files            = ("src/web/*.php", "src/apps/*/config/routing.yml"),
    excluded_folders = ("vendor", "src/apps/frontend/cache"),
    excluded_files   = ("*.min.js",),
)


@pytest.mark.parametrize(
    "path",
    [
        "src/lib/Urzad/Sesja/KontrolaSesji.php",    # PHP w folderze z listy
        "src/web/js/pisma/pisma.js",                # JS w folderze z listy
        "src/lib/Urzad/Poczta/powiadomienie.twig",  # szablon Twig
        "src/lib/Urzad/Sesja/KONTROLA.PHP",         # rozszerzenie wielkimi literami
    ],
)
def test_a_file_with_a_listed_extension_in_a_listed_folder_is_taken(path: str) -> None:
    """Sprawdza, czy plik z rozszerzeniem z listy, leżący w folderze z listy na dowolnej
    głębokości, wchodzi do paczki — także gdy rozszerzenie jest zapisane wielkimi literami.

    Wyłapuje dobór, który gubi kod własny aplikacji: narzędzia agenta nie znalazłyby wtedy pliku,
    w którym leży przyczyna zgłoszenia."""
    assert is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/apps/frontend/config/app.yml",  # YAML w folderze z listy: tu leżą hasła
        "src/lib/Urzad/klucz.pem",           # klucz w folderze z listy
        "src/lib/Urzad/LICENSE",             # plik bez rozszerzenia
        "src/config/databases.yml",          # poza folderami z listy
        "src/config/ustawienia.php",         # rozszerzenie z listy, folder spoza listy
        "src/library/Narzedzie.php",         # folder o nazwie zaczynającej się jak `src/lib`
    ],
)
def test_a_file_the_rules_do_not_name_is_not_taken(path: str) -> None:
    """Sprawdza, czy plik, którego reguły nie wymieniają, nie wchodzi do paczki: z rozszerzeniem
    spoza listy albo spoza folderów z listy, także z folderu o podobnie zaczynającej się nazwie.

    Wyłapuje dobór, który przepuszcza plik spoza listy włączeń: kod z paczki idzie do modelu
    zewnętrznego bez anonimizacji, a w takich plikach leżą hasła i klucze."""
    assert not is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/apps/frontend/config/routing.yml",  # YAML w folderze z listy, wskazany wprost
        "src/web/index.php",                     # plik spoza folderów z listy
    ],
)
def test_a_file_listed_explicitly_is_taken(path: str) -> None:
    """Sprawdza, czy plik pasujący do wzorca z `files` wchodzi do paczki bez względu na
    rozszerzenie i na to, czy leży w folderze z listy.

    Wyłapuje paczkę bez plików wskazanych wprost, czyli bez routingu i wejścia do aplikacji:
    bez nich nie da się przejść od adresu do akcji."""
    assert is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/web/narzedzia/naprawa.php",                 # katalog niżej niż `src/web/*.php`
        "src/apps/frontend/modules/config/routing.yml",  # o katalog więcej niż we wzorcu
        "src/apps/config/routing.yml",                   # o katalog mniej niż we wzorcu
    ],
)
def test_a_star_in_a_listed_file_stays_within_one_directory(path: str) -> None:
    """Sprawdza, czy gwiazdka we wzorcu z `files` zastępuje fragment nazwy tylko w obrębie jednego
    katalogu: plik leżący o katalog głębiej albo płycej, niż mówi wzorzec, nie wchodzi.

    Wyłapuje gwiazdkę przechodzącą przez ukośnik: wzorzec `src/web/*.php` brałby wtedy całe
    drzewo `src/web`, razem ze skryptami, których reguły nie wymieniają."""
    assert not is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/lib/vendor/pdfmaker/PdfMaker.php",          # katalog tuż pod folderem z listy
        "src/apps/frontend/lib/vendor/poczta/Mail.php",  # ten sam katalog głębiej
    ],
)
def test_a_folder_excluded_by_name_is_excluded_at_any_depth(path: str) -> None:
    """Sprawdza, czy wpis `excluded_folders` bez ukośnika wyłącza katalog o tej nazwie na każdej
    głębokości, razem ze wszystkim w środku.

    Wyłapuje wyłączenie działające tylko tuż pod folderem z listy: biblioteki zewnętrzne leżące
    głębiej weszłyby do paczki i zasypały wyniki szukania cudzym kodem."""
    assert not is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/lib/vendors/Lista.php",    # katalog o dłuższej nazwie
        "src/lib/my_vendor/Lista.php",  # nazwa katalogu kończąca się jak wpis
        "src/lib/Urzad/vendor.php",     # plik, nie katalog
    ],
)
def test_a_folder_name_excludes_only_a_directory_named_exactly_so(path: str) -> None:
    """Sprawdza, czy wpis `vendor` nie wyłącza katalogu, którego nazwa tylko zawiera to słowo, ani
    pliku o takiej nazwie.

    Wyłapuje wyłączenie dopasowywane po fragmencie nazwy: z paczki wypadałby po cichu kod własny
    aplikacji."""
    assert is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/apps/frontend/cache/konfiguracja.php",     # plik w wyłączonym katalogu
        "src/apps/frontend/cache/szablony/layout.php",  # podkatalog wyłączonego katalogu
    ],
)
def test_a_folder_excluded_by_path_is_excluded_with_everything_inside(path: str) -> None:
    """Sprawdza, czy wpis `excluded_folders` z ukośnikiem wyłącza wskazany katalog razem z jego
    podkatalogami.

    Wyłapuje wyłączenie, które przepuszcza pliki generowane w trakcie pracy aplikacji: do paczki
    weszłaby skompilowana konfiguracja, a z nią to, co aplikacja wczytała z plików z hasłami."""
    assert not is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/apps/backend/cache/Pamiec.php",           # katalog `cache` innej aplikacji
        "src/apps/frontend/cache2/Pamiec.php",         # katalog o nazwie zaczynającej się tak samo
        "src/lib/src/apps/frontend/cache/Pamiec.php",  # ta sama ścieżka, ale nie od korzenia
    ],
)
def test_a_folder_path_excludes_that_one_place_only(path: str) -> None:
    """Sprawdza, czy wpis z ukośnikiem wyłącza jedną ścieżkę liczoną od folderu wejściowego: nie
    obejmuje katalogu o tej samej nazwie w innym miejscu ani katalogu o podobnej nazwie obok.

    Wyłapuje wpis ze ścieżką działający jak wpis z samą nazwą: wyłączenie jednego katalogu cache
    wycinałoby z paczki kod własny z każdego katalogu `cache` w aplikacji."""
    assert is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/web/js/kalendarz.min.js",     # tuż pod folderem z listy
        "src/web/js/pisma/wykres.min.js",  # w podkatalogu
    ],
)
def test_a_file_excluded_by_name_is_excluded_in_any_directory(path: str) -> None:
    """Sprawdza, czy wzorzec z `excluded_files` wyłącza plik po samej nazwie, w dowolnym katalogu.

    Wyłapuje plik zminifikowany w paczce: cała biblioteka w jednej linii trafiałaby do wyników
    szukania i do odczytu, a model nic by z niej nie wyczytał."""
    assert not is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/web/js/pisma/minimum.js",  # nazwa tylko zawiera „min"
        "src/web/js/min.js",            # brak kropki przed „min"
    ],
)
def test_a_name_pattern_does_not_exclude_similar_names(path: str) -> None:
    """Sprawdza, czy wzorzec `*.min.js` nie wyłącza pliku, którego nazwa jest tylko podobna.

    Wyłapuje wzorzec dopasowywany po fragmencie: z paczki wypadałby po cichu kod własny
    aplikacji."""
    assert is_taken(path, RULES)


@pytest.mark.parametrize(
    "path",
    [
        "src/web/js/kalendarz.min.js",               # wyłączony po nazwie pliku
        "src/apps/frontend/cache/konfiguracja.php",  # wyłączony po katalogu
    ],
)
def test_an_exclusion_wins_over_a_file_listed_explicitly(path: str) -> None:
    """Sprawdza, czy plik pasujący do wzorca z `files` nie wchodzi do paczki, gdy ma wyłączoną
    nazwę albo leży w wyłączonym katalogu.

    Wyłapuje wzorzec z `files`, który omija wyłączenia: szeroki wpis w rodzaju „wszystkie pliki
    JS z tego katalogu" wciągałby z powrotem to, co reguły wyłączyły."""
    rules = dataclasses.replace(
        RULES,
        files = ("src/web/js/*.js", "src/apps/frontend/cache/*.php"),
    )

    assert is_listed_file(path, rules)
    assert not is_taken(path, rules)


@pytest.mark.parametrize(
    "path",
    [
        "src/web/js/KALENDARZ.MIN.JS",               # nazwa pliku wielkimi literami
        "src/web/js/kalendarz.Min.js",               # nazwa pliku z jedną wielką literą
        "src/lib/Vendor/pdfmaker/PdfMaker.php",      # katalog wyłączony po nazwie
        "src/apps/frontend/Cache/konfiguracja.php",  # katalog wyłączony po ścieżce
    ],
)
def test_exclusions_ignore_letter_case(path: str) -> None:
    """Sprawdza, czy wyłączenie obejmuje plik i katalog także wtedy, gdy ich nazwa różni się od
    wpisu w regułach tylko wielkością liter.

    Wyłapuje wyłączenia porównywane znak w znak: kod leży na dysku Windows, gdzie `Vendor`
    i `vendor` to ten sam katalog, więc biblioteka albo plik zminifikowany zapisane inną
    wielkością liter weszłyby do paczki mimo reguł."""
    assert not is_taken(path, RULES)


def test_an_exclusion_written_in_capitals_works_the_same() -> None:
    """Sprawdza, czy wpisy wyłączeń zapisane w regułach wielkimi literami wyłączają pliki
    i katalogi zapisane na dysku małymi.

    Wyłapuje porównanie, które sprowadza do małych liter tylko ścieżkę pliku: wpis `VENDOR`
    w regułach nie wyłączałby wtedy niczego i nie dawał żadnego błędu."""
    rules = dataclasses.replace(
        RULES,
        excluded_folders = ("VENDOR", "SRC/APPS/FRONTEND/CACHE"),
        excluded_files   = ("*.MIN.JS",),
    )

    assert not is_taken("src/lib/vendor/pdfmaker/PdfMaker.php", rules)
    assert not is_taken("src/apps/frontend/cache/konfiguracja.php", rules)
    assert not is_taken("src/web/js/kalendarz.min.js", rules)
