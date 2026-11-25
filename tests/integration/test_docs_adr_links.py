"""
Description:
Test linków do decyzji architektonicznych (ADR): każdy plik z `docs/adr/` stoi w spisie
README i ma link w CLAUDE.md, a każdy link do ADR prowadzi do istniejącego pliku. Czyta pliki
repo jak dane, bez stacku i bez modelu.

| sprawdzenie                | po co                                                    |
|----------------------------|----------------------------------------------------------|
| ADR w spisie README        | spis czyta się na początku każdej sesji                  |
| ADR z linkiem w CLAUDE.md  | przy regule w sekcji tematycznej agent trafia na decyzję |
| link prowadzi do pliku     | zmiana nazwy ADR nie zostawia martwego odesłania         |

O czym pamiętać przy zmianach: że link stoi w sekcji tematycznej swojej decyzji, a nie
gdziekolwiek w CLAUDE.md, test nie sprawdza — to zostaje przy przeglądzie.
"""

from tests._helpers.adr import adr_files, claude_md_links, readme_links


def test_every_adr_is_listed_in_the_readme() -> None:
    """Sprawdza, czy w `docs/adr/` leży co najmniej jeden ADR i czy każdy ma link w spisie
    decyzji w `docs/adr/README.md`.

    Wyłapuje ADR dopisany bez wiersza w spisie: agent, który na początku sesji czyta tylko spis,
    nie wie wtedy, że decyzja istnieje. Wyłapuje też zmianę wzoru nazwy, przy której test
    nie widziałby żadnego ADR i przechodził na pusto."""
    missing = set(adr_files()) - readme_links()

    assert adr_files(), "W docs/adr/ nie ma żadnego pliku ADR o nazwie z zasad README"
    assert not missing, f"ADR bez wiersza w spisie README: {sorted(missing)}"


def test_every_adr_is_linked_from_claude_md() -> None:
    """Sprawdza, czy każdy ADR z `docs/adr/` ma w CLAUDE.md co najmniej jeden link
    (`docs/adr/<plik>`).

    Wyłapuje ADR, którego reguła nie stoi w CLAUDE.md przy swojej decyzji: agent zmieniający
    ten obszar czyta sekcję tematyczną i nie zobaczy ani decyzji, ani jej powodów."""
    missing = set(adr_files()) - claude_md_links()

    assert not missing, f"ADR bez linku w CLAUDE.md: {sorted(missing)}"


def test_every_adr_link_points_to_an_existing_file() -> None:
    """Sprawdza, czy każdy link do ADR w CLAUDE.md i w spisie README prowadzi do pliku, który
    leży w `docs/adr/`.

    Wyłapuje martwy link po zmianie nazwy albo literówce w nazwie pliku: odesłanie wyglądałoby
    na poprawne, a prowadziłoby donikąd."""
    broken = (claude_md_links() | readme_links()) - set(adr_files())

    assert not broken, f"Link do ADR, którego nie ma: {sorted(broken)}"
