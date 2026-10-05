from app.core_util.html import strip_html


def test_strips_tags_and_unescapes_entities():
    """Sprawdza, czy z fragmentu HTML zostaje czysty tekst: znaczniki `<p>` znikają, a encja
    `&#039;` zamienia się w apostrof.

    Wyłapuje znaczniki albo encje zostawione w tekście: trafiłyby do promptu i do sparsowanego
    zgłoszenia jako śmieci między słowami."""
    assert strip_html("<p>Nie działa wysyłka&#039;</p>") == "Nie działa wysyłka'"


def test_block_tags_become_line_breaks():
    """Sprawdza, czy dwa akapity HTML stojące jeden za drugim zostają po zdjęciu znaczników
    w osobnych liniach: „Krok 1" w pierwszej, „Krok 2" w drugiej.

    Wyłapuje sklejenie akapitów: bez złamania linii wyszłoby „Krok 1Krok 2", czyli koniec jednego
    zdania zrośnięty z początkiem następnego."""
    # Bez tego "Krok 1</p><p>Krok 2" dałoby "Krok 1Krok 2".
    assert strip_html("<p>Krok 1</p><p>Krok 2</p>") == "Krok 1\nKrok 2"


def test_br_becomes_a_line_break():
    """Sprawdza, czy znacznik `<br />` zamienia się w złamanie linii: „Pierwsza" i „Druga" zostają
    w osobnych liniach.

    Wyłapuje pozycje listy sklejone w jedno słowo: w bazie źródłowej `<br />` oddziela pozycje list,
    więc po jego zwykłym usunięciu lista stałaby się jednym ciągiem."""
    assert strip_html("Pierwsza<br />Druga") == "Pierwsza\nDruga"


def test_entities_are_unescaped_after_tags_are_removed():
    """Sprawdza, czy znacznik zapisany encjami zostaje w tekście jako zwykłe znaki: z `&lt;p&gt;`
    w środku zdania wychodzi `<p>`, a reszta zdania jest bez zmian.

    Wyłapuje złą kolejność kroków: gdyby encje były rozwijane przed usuwaniem znaczników, tekst
    wpisany przez użytkownika stałby się znacznikiem i zniknął z treści."""
    # Gdyby unescape szedł pierwszy, "&lt;p&gt;" stałoby się "<p>" i zniknęłoby razem z treścią.
    assert strip_html("Wpisz &lt;p&gt; w polu") == "Wpisz <p> w polu"


def test_empty_html_gives_empty_string():
    """Sprawdza, czy puste wejście daje pusty tekst, bez wyjątku.

    Wyłapuje wyjątek albo dopisane znaki przy pustym wejściu: pole bez treści ma zostać puste, a nie
    przerywać czytania."""
    assert strip_html("") == ""
