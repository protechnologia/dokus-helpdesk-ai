from app.core_util.time import format_duration


def test_short_runs_stay_in_seconds():
    """Sprawdza, czy czas krótszy niż 90 sekund jest podawany w samych sekundach: 42,4 s to „42s".

    Wyłapuje dzielenie krótkiego czasu na minuty albo wypisywanie ułamka sekundy: przy tak krótkim
    przebiegu nic by to nie wyjaśniało, a utrudniało czytanie."""
    assert format_duration(42.4) == "42s"


def test_seconds_are_rounded_not_truncated():
    """Sprawdza, czy ułamek sekundy jest zaokrąglany, a nie obcinany: 89,6 s to „90s", nie „89s".

    Wyłapuje obcinanie ułamka: 89,6 s jest bliżej 90 niż 89, a po obcięciu każdy czas byłby zaniżony
    nawet o prawie całą sekundę."""
    assert format_duration(89.6) == "90s"


def test_longer_runs_switch_to_minutes():
    """Sprawdza, czy czas od 90 sekund w górę jest podawany w minutach i sekundach: 125 s to
    „2min 05s".

    Wyłapuje czas zostawiony w samych sekundach albo źle przeliczony na minuty: długie przebiegi
    trwają minuty, a przy zapisie „125s" czytający musiałby dzielić sam."""
    assert format_duration(125) == "2min 05s"


def test_seconds_are_zero_padded_in_minutes():
    """Sprawdza, czy sekundy w zapisie z minutami są dopełniane zerem: 125 s to „2min 05s".

    Wyłapuje zapis „2min 5s", który na pierwszy rzut oka czyta się jak 2 minuty 50 sekund."""
    assert format_duration(125) == "2min 05s"


def test_corpus_length_runs_switch_to_hours():
    """Sprawdza, czy czas dłuższy niż godzina jest podawany w godzinach i minutach: 3847,2 s to
    „1h 04min".

    Wyłapuje czas zostawiony w minutach albo źle przeliczony na godziny: tyle trwa przebieg po całym
    korpusie, a zapis w rodzaju „64min" kazałby czytającemu liczyć samemu."""
    assert format_duration(3847.2) == "1h 04min"


def test_exact_hour_reports_zero_minutes():
    """Sprawdza, czy równa godzina jest podawana z jawnymi minutami: 3600 s to „1h 00min", a nie
    samo „1h".

    Wyłapuje pomijanie zerowych minut: wynik miałby wtedy raz jedną, raz dwie części, a jego
    szerokość w wierszu podsumowania przestałaby być stała."""
    assert format_duration(3600) == "1h 00min"


def test_zero_is_rendered_not_blank():
    """Sprawdza, czy zero sekund daje „0s", a nie pusty tekst.

    Wyłapuje pusty wynik dla zera: wiersz podsumowania ma zawsze coś pokazać, a puste miejsce
    wyglądałoby jak brak pomiaru."""
    assert format_duration(0) == "0s"
