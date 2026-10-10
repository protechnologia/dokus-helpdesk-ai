from app.agent_tools.code.list_code_files import (
    DEFAULT_DEPTH,
    MAX_ENTRIES_PER_LISTING,
    CodeDirEntry,
    CodeDirInfo,
    FakeListCodeFilesTool,
    ListCodeFilesResult,
    RequestedDepth,
    ReturnedDepth,
)

# Opis `list_code_files` dla modelu podaje trzy rzeczy, które kod trzyma gdzie indziej: limit
# pozycji, domyślną głębokość i pola wyniku. Układ opisu sprawdza test kontraktu narzędzi; tu
# pilnujemy tylko tego, żeby opis i kod mówiły to samo.

DESCRIPTION = FakeListCodeFilesTool().description

# Pola wyniku pod pełną ścieżką, tak jak stoją w tabelce „Co zwraca". Nazwy pól zagnieżdżonych
# pochodzą z modeli, więc pole dopisane w modelu trafia tu samo.
RESULT_FIELDS = [
    "path",
    *[f"dir_info.{name}" for name in CodeDirInfo.model_fields],
    *[f"requested.{name}" for name in RequestedDepth.model_fields],
    *[f"returned.{name}" for name in ReturnedDepth.model_fields],
    *[f"entries[].{name}" for name in CodeDirEntry.model_fields],
]


def test_the_description_names_the_entry_limit_of_the_code() -> None:
    """Sprawdza, czy opis narzędzia podaje modelowi limit pozycji jednego spisu równy stałej
    `MAX_ENTRIES_PER_LISTING`, w zdaniu „najwyżej … pozycji".

    Wyłapuje zmianę limitu w kodzie bez zmiany opisu: model planowałby spisy pod inną liczbę
    pozycji, niż dostaje, i dowiadywał się o tym dopiero z uciętego wyniku."""
    assert f"najwyżej {MAX_ENTRIES_PER_LISTING} pozycji" in DESCRIPTION


def test_the_description_names_the_default_depth_of_the_code() -> None:
    """Sprawdza, czy opis narzędzia podaje modelowi domyślną głębokość równą stałej
    `DEFAULT_DEPTH`, w słowach „domyślnie …".

    Wyłapuje zmianę wartości domyślnej w kodzie bez zmiany opisu: model, który nie podał
    głębokości, dostawałby inną liczbę poziomów, niż obiecuje opis."""
    assert f"domyślnie {DEFAULT_DEPTH}." in DESCRIPTION


def test_the_description_explains_every_field_of_the_result() -> None:
    """Sprawdza, czy tabelka wyniku w opisie narzędzia wymienia każde pole, które model dostaje,
    pod pełną ścieżką (na przykład `returned.depth_cut_by_limit`), i czy wynik nie ma części
    górnego poziomu, o której ten test nie wie.

    Wyłapuje pole dopisane w modelu wyniku bez słowa w opisie: model widziałby je w odpowiedzi,
    ale nie wiedziałby, co znaczy — a od sygnałów głębokości zależy, czy ma szukać głębiej."""
    returns = DESCRIPTION.split("# Co zwraca")[1].split("# Zasady")[0]

    assert set(ListCodeFilesResult.model_fields) == {
        "path", "dir_info", "requested", "returned", "entries",
    }

    for field in RESULT_FIELDS:
        assert f"| {field} " in returns, field


def test_the_description_names_the_tools_that_take_the_listed_paths() -> None:
    """Sprawdza, czy zasady w opisie narzędzia wymieniają po nazwie odczyt pliku
    (`read_code_file`) i szukanie (`find_code_text`), którym model podaje ścieżki ze spisu.

    Wyłapuje opis po zmianie nazwy któregoś z tych narzędzi: model dostałby radę, żeby wywołać
    narzędzie, którego nie ma na jego liście."""
    rules = DESCRIPTION.split("# Zasady")[1]

    assert "`read_code_file`" in rules
    assert "`find_code_text`" in rules
