from app.agent_tools.base import label_matches


def test_matches_are_labelled_by_the_first_way_they_were_found() -> None:
    """Element znaleziony frazą i słowami → raz, jako `exact`, przed znalezionymi tylko słowami:
    trafienie po przepisanej frazie mówi więcej niż po słowach kluczowych."""
    matched = label_matches(exact_ids=["90011"], words_ids=["90012", "90011"])

    assert matched       == {"90011": "exact", "90012": "words"}
    assert list(matched) == ["90011", "90012"]


def test_each_way_keeps_its_own_order() -> None:
    """Kilka trafień każdą drogą → kolejność z bazy zostaje w obrębie drogi: słowa wracają od
    najlepiej dopasowanych i limit ma ciąć od końca tej listy."""
    matched = label_matches(exact_ids=["b", "a"], words_ids=["d", "c"])

    assert list(matched) == ["b", "a", "d", "c"]


def test_nothing_found_either_way_is_an_empty_list() -> None:
    """Brak trafień obiema drogami → pusta lista, nie błąd."""
    assert label_matches(exact_ids=[], words_ids=[]) == {}
