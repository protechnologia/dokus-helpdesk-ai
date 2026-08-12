from app.util.html import strip_html


def test_strips_tags_and_unescapes_entities():
    """HTML ze źródła → czysty tekst; tagi zdjęte, encje rozwinięte."""
    assert strip_html("<p>Nie działa wysyłka&#039;</p>") == "Nie działa wysyłka'"


def test_block_tags_become_line_breaks():
    """Akapity rozdzielone → nie sklejają się w jedno słowo po zdjęciu tagów."""
    # Bez tego "Krok 1</p><p>Krok 2" dałoby "Krok 1Krok 2".
    assert strip_html("<p>Krok 1</p><p>Krok 2</p>") == "Krok 1\nKrok 2"


def test_br_becomes_a_line_break():
    """<br /> → złamanie linii, bo w tej bazie oddziela pozycje list."""
    assert strip_html("Pierwsza<br />Druga") == "Pierwsza\nDruga"


def test_entities_are_unescaped_after_tags_are_removed():
    """Encja opisująca tag → zostaje tekstem, nie staje się tagiem do usunięcia."""
    # Gdyby unescape szedł pierwszy, "&lt;p&gt;" stałoby się "<p>" i zniknęłoby razem z treścią.
    assert strip_html("Wpisz &lt;p&gt; w polu") == "Wpisz <p> w polu"


def test_empty_html_gives_empty_string():
    """Puste wejście → pusty string, bez wyjątku."""
    assert strip_html("") == ""
