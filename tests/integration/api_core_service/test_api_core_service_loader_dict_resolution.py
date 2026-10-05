import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core_model.dicts.resolution_vocabulary import ResolutionVocabulary
from app.core_service.loader_dict_resolution import DEFAULT_DICT_FILE, get_resolution_classes


def test_bundled_vocabulary_loads() -> None:
    """Sprawdza, czy domyślny słownik rozstrzygnięć, dostarczany razem z aplikacją, daje się
    wczytać, ma numer wersji i co najmniej jedną klasę rozstrzygnięcia.

    Wyłapuje plik słownika, którego brakuje, który jest uszkodzony albo pusty: przy parsowaniu
    zgłoszeń nie byłoby wtedy żadnej klasy rozstrzygnięcia do wyboru."""
    vocabulary = get_resolution_classes()

    assert vocabulary.version >= 1
    assert vocabulary.classes


def test_every_class_carries_a_hint_for_the_prompt() -> None:
    """Sprawdza, czy każda klasa domyślnego słownika ma niepusty opis, czyli zdanie mówiące
    modelowi, co ta klasa znaczy.

    Wyłapuje klasę z samą nazwą: model nie wie wtedy, kiedy ją wybrać, i przypisuje ją
    zgłoszeniom na zgadywanie."""
    for entry in get_resolution_classes().classes:
        assert entry.hint.strip(), f"{entry.name} bez opisu dla promptu"


def test_class_names_are_unique() -> None:
    """Sprawdza, czy w domyślnym słowniku żadna nazwa klasy się nie powtarza.

    Wyłapuje tę samą nazwę wpisaną dwa razy: wartość zapisana w karcie zgłoszenia przestałaby
    mieć jedno znaczenie."""
    names = get_resolution_classes().names()

    assert len(names) == len(set(names))


def test_names_preserve_declaration_order() -> None:
    """Sprawdza, czy lista nazw klas wraca w tej samej kolejności, w jakiej klasy stoją w pliku
    słownika.

    Wyłapuje sortowanie albo przestawianie klas przy wczytaniu: prompt wymienia je w tej
    kolejności, więc jego treść zmieniłaby się, choć nikt nie ruszył pliku."""
    raw = json.loads(DEFAULT_DICT_FILE.read_text(encoding="utf-8"))

    assert get_resolution_classes().names() == [entry["name"] for entry in raw["classes"]]


def test_vocabulary_offers_an_exit_for_an_undecided_thread() -> None:
    """Sprawdza, czy domyślny słownik zawiera klasę `brak`, przeznaczoną dla wątku, który
    niczego nie rozstrzyga.

    Wyłapuje usunięcie tej klasy: takie wątki zdarzają się naprawdę, a bez tego wyjścia model
    musiałby przypisać zgłoszeniu rozstrzygnięcie, którego nie było."""
    assert "brak" in get_resolution_classes().names()


def test_vocabulary_can_be_loaded_from_another_file(tmp_path: Path) -> None:
    """Sprawdza, czy słownik da się wczytać ze wskazanego pliku zamiast z domyślnego: z pliku
    założonego w teście wraca wersja 7 i jedna klasa.

    Wyłapuje funkcję, która pomija podaną ścieżkę i zawsze oddaje słownik domyślny. Źródło
    słownika ma dać się podmienić bez zmian w kodzie, który o słownik pyta."""
    custom = tmp_path / "own_rules.json"
    custom.write_text(
        json.dumps({"version": 7, "classes": [{"name": "solved", "hint": "fixed"}]}),
        encoding="utf-8",
    )

    vocabulary = get_resolution_classes(custom)

    assert vocabulary.version == 7
    assert vocabulary.names() == ["solved"]


def test_malformed_vocabulary_is_rejected(tmp_path: Path) -> None:
    """Sprawdza, czy treść pliku słownika, w którym klasa ma nazwę, ale nie ma opisu, jest
    odrzucana błędem walidacji przez model słownika.

    Wyłapuje poluzowanie wymagań wobec słownika: wadliwy plik przeszedłby wtedy bez błędu,
    a usterka wyszłaby dopiero później, jako niepełny prompt."""
    broken = tmp_path / "broken_rules.json"
    broken.write_text(json.dumps({"version": 1, "classes": [{"name": "solved"}]}), encoding="utf-8")

    with pytest.raises(ValidationError):
        ResolutionVocabulary.model_validate_json(broken.read_text(encoding="utf-8"))
