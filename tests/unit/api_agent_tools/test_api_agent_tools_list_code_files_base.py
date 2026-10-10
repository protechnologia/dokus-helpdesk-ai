from app.agent_tools.code.list_code_files import (
    MAX_ENTRIES_PER_LISTING,
    ROOT_DIR,
    ListCodeFilesQuery,
    select_entries_and_build_result,
)

# Wybieranie pozycji jest wspólne dla narzędzia i atrapy, więc sprawdzamy je raz, na ścieżkach
# plików podanych wprost, bez dysku. Katalogi powstają w nim ze ścieżek plików.

WYSYLKA = "src/lib/Urzad/Wysylka"

# Pliki pod katalogiem `WYSYLKA`: dwa podkatalogi po jednym pliku i plik obok nich.
FILES = [
    f"{WYSYLKA}/Edoreczenia/PobieranieSkrzynki.php",
    f"{WYSYLKA}/Epuap/WysylkaEpuap.php",
    f"{WYSYLKA}/LimitZalacznika.php",
]

# Siatka do testu zgodności sygnałów z liczbami: ile podkatalogów ma katalog, ile plików leży
# w każdym podkatalogu, ile plików leży wprost w katalogu i o jaką głębokość prosi agent.
GRID = [
    (dirs, files_per_dir, files, depth)
    for dirs in (0, 1, 3, MAX_ENTRIES_PER_LISTING, MAX_ENTRIES_PER_LISTING + 1)
    for files_per_dir in (1, 2, 70)
    for files in (0, 1, 5, MAX_ENTRIES_PER_LISTING, MAX_ENTRIES_PER_LISTING + 5)
    for depth in (1, 2, 3)
    if dirs or files
]


def _tree(
    dirs:          int,  # np. 3 — podkatalogi katalogu „kod"
    files_per_dir: int,  # np. 2 — pliki w każdym podkatalogu
    files:         int,  # np. 5 — pliki wprost w katalogu „kod"
) -> list[str]:
    """
    Description:
    Buduje ścieżki plików zmyślonego katalogu `kod`: podkatalogi `d000`, `d001`… z plikami
    `p000.php`… i pliki `f000.php`… wprost w katalogu.

    Example args:
        dirs=1
        files_per_dir=2
        files=1

    Example result:
        ["kod/d000/p000.php", "kod/d000/p001.php", "kod/f000.php"]
    """
    nested = [
        f"kod/d{directory:03}/p{file:03}.php"
        for directory in range(dirs)
        for file in range(files_per_dir)
    ]
    flat = [f"kod/f{file:03}.php" for file in range(files)]

    return nested + flat


def test_one_level_shows_the_directory_itself() -> None:
    """Sprawdza, czy spis jednego poziomu pokazuje pozycje samego katalogu: dwa podkatalogi
    i plik, każdą z pełną ścieżką i rodzajem, a plików z podkatalogów nie pokazuje. Wynik mówi
    przy tym, że katalog ma dwa poziomy i że głębiej coś jeszcze jest.

    Wyłapuje spis, który przy jednym poziomie schodzi w podkatalogi albo oddaje same nazwy:
    model nie mógłby podać pozycji odczytowi pliku bez sklejania jej z nazwą katalogu."""
    result = select_entries_and_build_result(ListCodeFilesQuery(depth=1), WYSYLKA, FILES)

    assert [(entry.path, entry.kind) for entry in result.entries] == [
        (f"{WYSYLKA}/Edoreczenia",         "dir"),
        (f"{WYSYLKA}/Epuap",               "dir"),
        (f"{WYSYLKA}/LimitZalacznika.php", "file"),
    ]
    assert result.path                 == WYSYLKA
    assert result.dir_info.total_depth == 2
    assert result.requested.depth      == 1
    assert result.returned.model_dump() == {
        "depth": 1, "depth_cut_by_limit": False, "has_more_depth": True, "omitted_over_limit": 0,
    }


def test_two_levels_put_every_directory_right_above_its_content() -> None:
    """Sprawdza, czy spis dwóch poziomów stawia każdy podkatalog tuż nad jego plikami,
    a podkatalogi przed plikiem leżącym obok nich, i czy mówi, że głębiej nic już nie ma.

    Wyłapuje spis ułożony poziomami albo zwykłym alfabetem: plik stałby wtedy daleko od swojego
    katalogu, a model czytałby listę jak płaski zbiór ścieżek, bez widocznej struktury."""
    result = select_entries_and_build_result(ListCodeFilesQuery(depth=2), WYSYLKA, FILES)

    assert [(entry.path, entry.kind) for entry in result.entries] == [
        (f"{WYSYLKA}/Edoreczenia",                        "dir"),
        (f"{WYSYLKA}/Edoreczenia/PobieranieSkrzynki.php", "file"),
        (f"{WYSYLKA}/Epuap",                              "dir"),
        (f"{WYSYLKA}/Epuap/WysylkaEpuap.php",             "file"),
        (f"{WYSYLKA}/LimitZalacznika.php",                "file"),
    ]
    assert result.returned.model_dump() == {
        "depth": 2, "depth_cut_by_limit": False, "has_more_depth": False, "omitted_over_limit": 0,
    }


def test_directories_stand_before_files_whatever_their_names() -> None:
    """Sprawdza, czy w jednym katalogu podkatalogi stoją przed plikami także wtedy, gdy nazwa
    pliku jest w alfabecie wcześniej niż nazwa podkatalogu.

    Wyłapuje sortowanie po samej nazwie: w katalogu ponad limit model zobaczyłby wtedy początek
    plików, a podkatalogi, po których idzie się dalej, wypadłyby z wyniku."""
    files  = ["kod/aaa.php", "kod/zzz/plik.php", "kod/mmm.php"]
    result = select_entries_and_build_result(ListCodeFilesQuery(depth=1), "kod", files)

    assert [(entry.path, entry.kind) for entry in result.entries] == [
        ("kod/zzz",     "dir"),
        ("kod/aaa.php", "file"),
        ("kod/mmm.php", "file"),
    ]


def test_a_depth_larger_than_the_directory_stops_where_the_directory_ends() -> None:
    """Sprawdza, czy prośba o dziewięć poziomów katalogu, który ma dwa, oddaje dwa poziomy, nie
    oznacza zmniejszenia głębokości przez limit i mówi, że głębiej nic nie ma; w żądanej
    głębokości zostaje 9.

    Wyłapuje głębokość ponad to, co katalog ma, zgłaszaną jako ucięcie limitem albo jako błąd:
    model nie zna głębokości katalogu przed pierwszym spisem, a po fladze limitu szukałby
    pozycji, których nie ma."""
    result = select_entries_and_build_result(ListCodeFilesQuery(depth=9), WYSYLKA, FILES)

    assert len(result.entries)    == 5
    assert result.requested.depth == 9
    assert result.returned.model_dump() == {
        "depth": 2, "depth_cut_by_limit": False, "has_more_depth": False, "omitted_over_limit": 0,
    }


def test_the_code_root_lists_paths_without_a_prefix() -> None:
    """Sprawdza, czy spis katalogu głównego kodu (ścieżka `.`) oddaje pozycje ze ścieżkami
    liczonymi od tego katalogu, bez `./` na początku, i liczy głębokość od niego.

    Wyłapuje katalog główny potraktowany jak zwykły katalog o nazwie `.`: pozycje miałyby
    ścieżki `./src`, których żadne narzędzie kodu nie zwraca, albo spis byłby pusty."""
    result = select_entries_and_build_result(ListCodeFilesQuery(depth=1), ROOT_DIR, FILES)

    assert [(entry.path, entry.kind) for entry in result.entries] == [("src", "dir")]
    assert result.path                 == "."
    assert result.dir_info.total_depth == 6


def test_a_depth_that_does_not_fit_the_limit_is_cut_to_whole_levels() -> None:
    """Sprawdza, czy prośba o dwa poziomy katalogu, w którym drugi poziom nie mieści się
    w limicie pozycji (3 podkatalogi po 70 plików to 213 pozycji), oddaje jeden pełny poziom,
    oznacza zmniejszenie głębokości i nie liczy żadnej pominiętej pozycji.

    Wyłapuje poziom ucięty w połowie: model widziałby pliki pierwszego podkatalogu, a pozostałe
    podkatalogi wyglądałyby na puste, bez żadnego znaku, że to limit."""
    result = select_entries_and_build_result(
        ListCodeFilesQuery(depth=2), "kod", _tree(dirs=3, files_per_dir=70, files=0),
    )

    assert [entry.path for entry in result.entries] == ["kod/d000", "kod/d001", "kod/d002"]
    assert result.returned.model_dump() == {
        "depth": 1, "depth_cut_by_limit": True, "has_more_depth": True, "omitted_over_limit": 0,
    }


def test_levels_that_fit_exactly_are_not_cut() -> None:
    """Sprawdza granicę limitu: dwa poziomy, które razem dają dokładnie tyle pozycji, ile
    wynosi limit, wracają w całości i bez flagi, a jedna pozycja więcej zmniejsza głębokość.

    Wyłapuje granicę przesuniętą o jeden: spis mieszczący się na styk byłby ucinany bez
    potrzeby albo wynik miałby pozycję ponad limit."""
    at_the_limit = _tree(dirs=4, files_per_dir=49, files=0)   # 4 + 196 = 200 pozycji
    one_more     = at_the_limit + ["kod/f000.php"]            # 5 + 196 = 201 pozycji

    fits = select_entries_and_build_result(ListCodeFilesQuery(depth=2), "kod", at_the_limit)
    cut  = select_entries_and_build_result(ListCodeFilesQuery(depth=2), "kod", one_more)

    assert len(fits.entries)               == MAX_ENTRIES_PER_LISTING
    assert fits.returned.depth             == 2
    assert fits.returned.depth_cut_by_limit is False
    assert (cut.returned.depth, len(cut.entries)) == (1, 5)
    assert cut.returned.depth_cut_by_limit is True


def test_a_directory_over_the_limit_shows_its_directories_first_and_counts_the_rest() -> None:
    """Sprawdza, czy spis katalogu, który sam ma więcej pozycji niż limit (2 podkatalogi
    i 205 plików), oddaje dokładnie tyle pozycji, ile wynosi limit, zaczyna od obu podkatalogów
    i podaje liczbę pominiętych plików; głębokości przy tym nie oznacza jako zmniejszonej,
    bo agent prosił o jeden poziom.

    Wyłapuje wynik bez limitu, który wkleja modelowi katalog z tysiącem plików, oraz ucięcie
    bez licznika: model uznałby, że zobaczył cały katalog."""
    result = select_entries_and_build_result(
        ListCodeFilesQuery(depth=1),
        "kod",
        _tree(dirs=2, files_per_dir=1, files=MAX_ENTRIES_PER_LISTING + 5),
    )

    assert len(result.entries) == MAX_ENTRIES_PER_LISTING
    assert [entry.kind for entry in result.entries[:3]] == ["dir", "dir", "file"]
    assert result.returned.model_dump() == {
        "depth": 1, "depth_cut_by_limit": False, "has_more_depth": True, "omitted_over_limit": 7,
    }


def test_a_flat_directory_over_the_limit_has_nothing_deeper() -> None:
    """Sprawdza, czy spis katalogu z samymi plikami, których jest więcej niż limit, liczy
    pominięte pliki, ale nie mówi, że głębiej coś jest: katalog ma jeden poziom.

    Wyłapuje flagę głębokości ustawianą przy każdym ucięciu: model szukałby podkatalogów
    w katalogu, który ich nie ma, zamiast przeszukać ten katalog po treści."""
    result = select_entries_and_build_result(
        ListCodeFilesQuery(depth=2),
        "kod",
        _tree(dirs=0, files_per_dir=1, files=MAX_ENTRIES_PER_LISTING + 30),
    )

    assert result.dir_info.total_depth == 1
    assert result.returned.model_dump() == {
        "depth": 1, "depth_cut_by_limit": False, "has_more_depth": False, "omitted_over_limit": 30,
    }


def test_the_signals_always_agree_with_the_numbers() -> None:
    """Sprawdza na siatce kształtów katalogu (liczba podkatalogów, plików w podkatalogu i plików
    wprost w katalogu) i żądanych głębokości, czy sygnały zawsze wynikają z liczb: pozycji nigdy
    nie jest więcej niż limit, pominięte są liczone tylko wtedy, gdy sam katalog nie mieści się
    w limicie, i razem z pokazanymi dają komplet pierwszego poziomu, a bez pominiętych wynik ma
    dokładnie tyle pozycji, ile leży na pokazanych poziomach. Zmniejszenie głębokości jest
    oznaczone dokładnie wtedy, gdy agent prosił o poziom, który istnieje, a go nie dostał,
    a „głębiej jest więcej" dokładnie wtedy, gdy katalog ma poziom poniżej pokazanych.

    Wyłapuje sygnał, który przeczy liczbom w jakimś rzadkim układzie: model wierzy sygnałom,
    więc przestałby szukać głębiej tam, gdzie coś jest, albo uznał ucięty katalog za pełny."""
    for dirs, files_per_dir, files, depth in GRID:
        # Kształt katalogu trafia do komunikatu asercji, żeby po porażce było widać, który zawiódł.
        case   = f"podkatalogi {dirs} po {files_per_dir} plików, plików {files}, głębokość {depth}"
        result = select_entries_and_build_result(
            ListCodeFilesQuery(depth=depth), "kod", _tree(dirs, files_per_dir, files),
        )

        returned    = result.returned
        level_one   = dirs + files
        level_two   = dirs * files_per_dir
        total_depth = 2 if dirs else 1
        on_levels   = level_one + (level_two if returned.depth == 2 else 0)

        assert result.dir_info.total_depth == total_depth, case
        assert len(result.entries)         <= MAX_ENTRIES_PER_LISTING, case
        assert 1 <= returned.depth         <= min(depth, total_depth), case

        if level_one > MAX_ENTRIES_PER_LISTING:
            assert returned.depth                                  == 1, case
            assert len(result.entries) + returned.omitted_over_limit == level_one, case
        else:
            assert returned.omitted_over_limit == 0, case
            assert len(result.entries)         == on_levels, case

        assert returned.depth_cut_by_limit == (returned.depth < min(depth, total_depth)), case
        assert returned.has_more_depth     == (returned.depth < total_depth), case


def test_every_entry_is_listed_once_and_under_the_listed_directory() -> None:
    """Sprawdza, czy w spisie całego katalogu każda pozycja stoi raz, każda leży pod spisanym
    katalogiem, a plików jest dokładnie tyle, ile ścieżek podano.

    Wyłapuje podkatalog wpisany osobno dla każdego swojego pliku oraz pozycję spoza spisanego
    katalogu: model liczyłby pliki katalogu z listy, na której część stoi dwa razy."""
    result = select_entries_and_build_result(
        ListCodeFilesQuery(depth=9), "kod", _tree(dirs=3, files_per_dir=4, files=2),
    )
    paths = [entry.path for entry in result.entries]

    assert len(paths) == len(set(paths)) == 3 + 12 + 2
    assert all(path.startswith("kod/") for path in paths)
    assert sum(entry.kind == "file" for entry in result.entries) == 14


def test_a_directory_without_files_gives_an_empty_listing() -> None:
    """Sprawdza, czy spis katalogu, pod którym nie leży żaden plik, jest pusty: bez pozycji,
    z głębokością zero i bez żadnego sygnału.

    Wyłapuje błąd liczenia na pustym katalogu: paczka pustych katalogów nie zawiera, ale atrapa
    zbudowana bez plików ma oddać „nic tu nie ma", a nie przerwać sprawę wyjątkiem."""
    result = select_entries_and_build_result(ListCodeFilesQuery(), ROOT_DIR, [])

    assert result.entries              == []
    assert result.dir_info.total_depth == 0
    assert result.returned.model_dump() == {
        "depth": 0, "depth_cut_by_limit": False, "has_more_depth": False, "omitted_over_limit": 0,
    }
