from functools import lru_cache
from pathlib import Path

from app.core_model.dict_resolution_vocabulary import ResolutionVocabulary

# Wbudowany zestaw domyślny. Magazyn reguł w SQL (p. 29) podmienia to ŹRÓDŁO, a ta funkcja jest
# szwem, który czyni podmianę niewidoczną: każdy wołający pyta o słownik tutaj, więc żaden nie
# dowie się, skąd przyszedł (CLAUDE.md -> „Bramki jakości": tą samą drogą idą reguły bramek
# i zasady stylu „Popraw"). Pakietu `rules/` już nie ma — szwem jest ta funkcja, a kolejne źródła
# stają obok niej jako siostrzane `loader_*` (jak `loader_dict_rules.py`), nie jako katalog.
DEFAULT_DICT_FILE = Path(__file__).parent.parent / "core_text" / "dict_resolution.json"


@lru_cache
def get_resolution_classes(path: Path = DEFAULT_DICT_FILE) -> ResolutionVocabulary:
    """
    Description:
    Wczytuje słownik rozstrzygnięć. Pamiętany per ścieżka, a nie czytany przy imporcie, więc
    import modułu nie dotyka dysku, a test może wskazać własny plik.

    Example args:
        path=Path("/code/app/core_text/dict_resolution.json")

    Example result:
        ResolutionVocabulary(version=1, classes=[ResolutionClass(name="naprawione", …), …])

    Raises:
        FileNotFoundError: brak pliku słownika — błąd wdrożenia, nie wykonania
    """
    return ResolutionVocabulary.model_validate_json(path.read_text(encoding="utf-8"))
