"""
Description:
Test linków do runbooków: każdy plik z `docs/runbook/` stoi w spisie README i ma link
w CLAUDE.md, a każdy link do runbooka prowadzi do istniejącego pliku. Czyta pliki repo jak dane,
bez stacku i bez modelu.

| sprawdzenie                   | po co                                                       |
|-------------------------------|-------------------------------------------------------------|
| runbook w spisie README       | spis mówi, jakie procedury są spisane                       |
| runbook z linkiem w CLAUDE.md | przy regule w sekcji tematycznej agent trafia na procedurę  |
| link prowadzi do pliku        | zmiana nazwy runbooka nie zostawia martwego odesłania       |

O czym pamiętać przy zmianach: że link stoi w sekcji tematycznej swojej procedury, a nie
gdziekolwiek w CLAUDE.md, test nie sprawdza — to zostaje przy przeglądzie.
"""

from tests._helpers.runbook import claude_md_links, readme_links, runbook_files


def test_every_runbook_is_listed_in_the_readme() -> None:
    """Sprawdza, czy w `docs/runbook/` leży co najmniej jeden runbook i czy każdy ma link
    w spisie w `docs/runbook/README.md`.

    Wyłapuje runbook dopisany bez wiersza w spisie: kto szuka procedury w spisie, nie wie wtedy,
    że jest spisana. Wyłapuje też zmianę wzoru nazwy, przy której test nie widziałby żadnego
    runbooka i przechodził na pusto."""
    missing = set(runbook_files()) - readme_links()

    assert runbook_files(), "W docs/runbook/ nie ma żadnego runbooka o nazwie z zasad README"
    assert not missing, f"Runbook bez wiersza w spisie README: {sorted(missing)}"


def test_every_runbook_is_linked_from_claude_md() -> None:
    """Sprawdza, czy każdy runbook z `docs/runbook/` ma w CLAUDE.md co najmniej jeden link
    (`docs/runbook/<plik>`).

    Wyłapuje runbook, którego reguła nie stoi w CLAUDE.md przy swojej procedurze: agent, który
    czyta sekcję tematyczną przed czynnością, nie trafi na spisane kroki i zrobi ją z pamięci."""
    missing = set(runbook_files()) - claude_md_links()

    assert not missing, f"Runbook bez linku w CLAUDE.md: {sorted(missing)}"


def test_every_runbook_link_points_to_an_existing_file() -> None:
    """Sprawdza, czy każdy link do runbooka w CLAUDE.md i w spisie README prowadzi do pliku,
    który leży w `docs/runbook/`.

    Wyłapuje martwy link po zmianie nazwy albo literówce w nazwie pliku: odesłanie wyglądałoby
    na poprawne, a prowadziłoby donikąd."""
    broken = (claude_md_links() | readme_links()) - set(runbook_files())

    assert not broken, f"Link do runbooka, którego nie ma: {sorted(broken)}"
