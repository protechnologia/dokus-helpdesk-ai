"""
Description:
Testy jednostkowe odczytu gałęzi z treści pliku `plastic.selector` (`branch_of_selector` ze
`scripts/build_code_package.py`). Plik pisze klient PlasticSCM w kopii roboczej; skrypt paczki
bierze z niego nazwę gałęzi do metryczki. Sam odczyt pliku z folderu sprawdzają testy
integracyjne budowy paczki.
"""

import pytest
from build_code_package import branch_of_selector

# Układ pliku z kopii roboczej: wcięcia i długi ogon spacji po nazwie gałęzi, jak w prawdziwym.
SMART_BRANCH = (
    'repository "aplikacja@serwer"\n'
    '  path "/"\n'
    '    smartbranch "/main/stage-gminy/zadanie-12"' + " " * 40 + "\n"
    "     \n"
)


def test_the_branch_of_a_working_copy_is_read() -> None:
    """Sprawdza, czy z treści pliku kopii roboczej stojącej na gałęzi wraca pełna nazwa tej
    gałęzi, bez cudzysłowów i bez spacji, którymi klient dopełnia linię.

    Wyłapuje odczyt, który bierze nazwę repozytorium zamiast gałęzi albo zostawia w nazwie
    cudzysłów: metryczka mówiłaby wtedy o innym kodzie niż ten, który jest w paczce."""
    assert branch_of_selector(SMART_BRANCH) == "/main/stage-gminy/zadanie-12"


def test_a_plain_branch_line_is_read_like_a_smart_one() -> None:
    """Sprawdza, czy gałąź zapisana słowem `branch` wraca tak samo jak zapisana słowem
    `smartbranch`.

    Wyłapuje odczyt znający tylko jeden zapis: kopia robocza ustawiona starszym sposobem dawałaby
    metryczkę bez gałęzi, choć gałąź jest w pliku."""
    assert branch_of_selector('repository "a@b"\n  path "/"\n    branch "/main"\n') == "/main"


@pytest.mark.parametrize(
    "text",
    ['repository "a@b"\n  path "/"\n    label "wydanie-4.12"\n', ""],
    ids=["etykieta", "pusty plik"],
)
def test_a_selector_without_a_branch_gives_none(text: str) -> None:
    """Sprawdza, czy plik, który nie wskazuje gałęzi — kopia robocza ustawiona na etykietę albo
    plik pusty — daje brak gałęzi, a nie wyjątek ani przypadkowy napis.

    Wyłapuje odczyt, który przy nietypowej kopii roboczej przerywa budowę paczki albo wpisuje do
    metryczki etykietę jako gałąź."""
    assert branch_of_selector(text) is None
