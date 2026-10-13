import pytest

from app.core_util.path import is_path_under


@pytest.mark.parametrize(
    ("path", "parent", "under"),
    [
        ("src/lib/Urzad/Numer.php", "src/lib",                 True),
        ("src/lib/Urzad/Numer.php", "src/lib/Urzad",           True),
        ("src/lib/Urzad/Numer.php", "src/lib/Urzad/Numer.php", True),
        ("src/lib",                 "src/lib",                 True),
        ("src/lib2/Numer.php",      "src/lib",                 False),
        ("src/lib/Numer.php2",      "src/lib/Numer.php",       False),
        ("src/web/js/okna.js",      "src/lib",                 False),
        ("src",                     "src/lib",                 False),
    ],
    ids=[
        "plik w katalogu", "plik głębiej", "ten sam plik", "ten sam katalog",
        "katalog o dłuższej nazwie", "plik o dłuższej nazwie", "inny katalog", "katalog wyżej",
    ],
)
def test_a_path_is_under_itself_and_under_its_directories(
    path:   str,
    parent: str,
    under:  bool,
) -> None:
    """Sprawdza, czy ścieżka leży pod podaną ścieżką wtedy, gdy jest nią samą albo leży w niej
    jako w katalogu, na dowolnej głębokości — i tylko wtedy.

    Wyłapuje porównanie samych początków napisów: katalog `src/lib2` uchodziłby za część
    `src/lib`, więc zawężenie do katalogu obejmowałoby pliki sąsiedniego."""
    assert is_path_under(path, parent) is under
