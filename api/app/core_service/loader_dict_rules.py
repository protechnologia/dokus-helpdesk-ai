from functools import lru_cache
from pathlib import Path

from app.core_model.dicts.rule_set import RuleSet

# Wbudowane zestawy domyślne, po jednym na graf z regułami. Magazyn reguł (p. 29) podmienia ŹRÓDŁO
# — wołający pytają o zestaw tutaj, więc żaden z nich nie dowie się, skąd przyszedł.
TEXT_DIR = Path(__file__).parent.parent / "core_text"


@lru_cache
def get_rule_set(
    graph: str,  # np. "gate_close"
) -> RuleSet:
    """
    Description:
    Wczytuje zestaw reguł grafu z `core_text/dict_rules_<graf>.json`. Pamiętany per graf, więc
    plik jest czytany raz na proces, a nie przy każdym żądaniu.

    Example args:
        graph="gate_close"

    Example result:
        RuleSet(version=1, rules=["Z treści wynika, co było problemem.", …])

    Raises:
        FileNotFoundError: brak zestawu dla grafu — błąd wdrożenia, nie żądania
        ValidationError: zestaw pusty albo bez wersji
    """
    path = TEXT_DIR / f"dict_rules_{graph}.json"

    return RuleSet.model_validate_json(path.read_text(encoding="utf-8"))
