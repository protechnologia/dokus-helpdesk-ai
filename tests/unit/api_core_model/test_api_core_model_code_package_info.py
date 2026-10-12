from datetime import date

import pytest
from pydantic import ValidationError

from app.core_model.code.code_package_info import CodePackageInfo


def test_the_branch_may_be_unknown_but_must_be_said() -> None:
    """Sprawdza, czy metryczka paczki przyjmuje gałąź równą `None`, ale odrzuca brak pola
    `branch`.

    Wyłapuje model, w którym gałąź ma wartość domyślną: metryczka bez tego pola wyglądałaby
    wtedy jak paczka z folderu, który nie jest kopią roboczą, choć skrypt po prostu go nie
    zapisał."""
    assert CodePackageInfo(branch=None, built_on="2026-10-07").branch is None

    with pytest.raises(ValidationError):
        CodePackageInfo(built_on="2026-10-07")


def test_the_build_day_is_a_date() -> None:
    """Sprawdza, czy dzień budowy zapisany w metryczce jako napis `2026-10-07` staje się datą,
    a napis, który datą nie jest, kończy się wyjątkiem `ValidationError`.

    Wyłapuje dzień budowy trzymany jako dowolny napis: model dostawałby w opisie projektu
    wartość, której nie da się odczytać jako dnia."""
    assert CodePackageInfo(branch="/main", built_on="2026-10-07").built_on == date(2026, 10, 7)

    with pytest.raises(ValidationError):
        CodePackageInfo(branch="/main", built_on="wczoraj")


@pytest.mark.parametrize(
    "fields",
    [
        {"branch": "", "built_on": "2026-10-07"},
        {"branch": "/main", "built_on": "2026-10-07", "changeset": 51962},
    ],
    ids=["pusta gałąź", "nieznane pole"],
)
def test_an_empty_branch_and_an_unknown_field_are_refused(fields: dict) -> None:
    """Sprawdza, czy pusta nazwa gałęzi i pole spoza modelu (`changeset`) kończą się wyjątkiem
    `ValidationError`.

    Wyłapuje model, który bierze pusty napis za gałąź: tytuł źródła z kodu kończyłby się wtedy
    dopiskiem „(gałąź )"."""
    with pytest.raises(ValidationError):
        CodePackageInfo(**fields)
