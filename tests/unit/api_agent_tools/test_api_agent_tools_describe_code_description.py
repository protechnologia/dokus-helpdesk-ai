from app.agent_tools.code.describe_code import DescribeCodeResult, FakeDescribeCodeTool
from app.core_model.code.code_package_info import CodePackageInfo

# Opis NARZĘDZIA `describe_code` dla modelu (plik `description.md` w katalogu narzędzia) podaje
# pola wyniku, które kod trzyma w modelach. Układ opisu sprawdza test kontraktu narzędzi; tu
# pilnujemy tylko tego, żeby opis i kod mówiły to samo.

DESCRIPTION = FakeDescribeCodeTool().description

# Pola wyniku pod pełną ścieżką, tak jak stoją w tabelce „Co zwraca".
RESULT_FIELDS = [
    *[f"package_info.{name}" for name in CodePackageInfo.model_fields],
    "description",
]


def test_the_description_explains_every_field_of_the_result() -> None:
    """Sprawdza, czy tabelka wyniku w opisie narzędzia wymienia każde pole, które model
    dostaje, pod pełną ścieżką (na przykład `package_info.branch`), i czy wynik nie ma części
    górnego poziomu, o której ten test nie wie.

    Wyłapuje pole dopisane w modelu wyniku bez słowa w opisie: model widziałby je w odpowiedzi,
    ale nie wiedziałby, co znaczy."""
    returns = DESCRIPTION.split("# Co zwraca")[1].split("# Zasady")[0]

    assert set(DescribeCodeResult.model_fields) == {"package_info", "description"}

    for field in RESULT_FIELDS:
        assert f"| {field} " in returns, field


def test_the_description_names_the_tools_of_the_way_from_a_directory_to_the_code() -> None:
    """Sprawdza, czy zasady w opisie narzędzia wymieniają po nazwie szukanie
    (`find_code_text`), spis katalogu (`list_code_files`) i odczyt pliku (`read_code_file`),
    w tej kolejności.

    Wyłapuje opis po zmianie nazwy któregoś z tych narzędzi albo z odczytem przed spisem:
    z opisu projektu model bierze katalog, a katalogu nie da się przeczytać."""
    rules     = DESCRIPTION.split("# Zasady")[1]
    positions = [
        rules.index("`find_code_text`"),
        rules.index("`list_code_files`"),
        rules.index("`read_code_file`"),
    ]

    assert positions == sorted(positions)


def test_the_description_says_the_code_comes_from_one_branch() -> None:
    """Sprawdza, czy zasady w opisie narzędzia mówią, że kod pochodzi z jednej gałęzi,
    i wskazują pole `package_info.branch`.

    Wyłapuje opis, z którego to zdanie wypadło: model brałby kod z paczki za stan instalacji
    klienta, choć klienci mają własne gałęzie."""
    rules = DESCRIPTION.split("# Zasady")[1]

    assert "`package_info.branch`" in rules
    assert "Instalacja klienta może stać na innej" in rules
