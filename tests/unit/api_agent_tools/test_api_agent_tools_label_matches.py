from app.agent_tools.base import label_matches


def test_matches_are_labelled_by_the_first_way_they_were_found() -> None:
    """Sprawdza, czy element znaleziony i frazą, i słowami (tu `90011`) jest w wyniku raz,
    z etykietą `exact`, i stoi przed elementem znalezionym tylko słowami (`90012`).

    Wyłapuje element powtórzony albo oznaczony jako znaleziony słowami: trafienie po przepisanej
    frazie mówi więcej niż po słowach kluczowych, więc model dostałby słabszą informację."""
    matched = label_matches(exact_ids=["90011"], words_ids=["90012", "90011"])

    assert matched       == {"90011": "exact", "90012": "words"}
    assert list(matched) == ["90011", "90012"]


def test_each_way_keeps_its_own_order() -> None:
    """Sprawdza, czy trafienia każdej drogi zostają w kolejności, w jakiej przyszły: znalezione
    frazą `b`, `a` i znalezione słowami `d`, `c` dają wynik `b`, `a`, `d`, `c`.

    Wyłapuje przestawianie trafień po drodze: baza oddaje słowa od najlepiej dopasowanych,
    a limit tnie listę od końca, więc po przestawieniu odpadałyby lepsze trafienia zamiast
    gorszych."""
    matched = label_matches(exact_ids=["b", "a"], words_ids=["d", "c"])

    assert list(matched) == ["b", "a", "d", "c"]


def test_nothing_found_either_way_is_an_empty_list() -> None:
    """Sprawdza, czy brak trafień obiema drogami, frazą i słowami, daje pusty wynik.

    Wyłapuje błąd przy pustych listach: brak trafień to zwykły wynik wyszukiwania, a nie
    usterka."""
    assert label_matches(exact_ids=[], words_ids=[]) == {}
