import importlib
import pkgutil
from types import ModuleType

import app.graph

# Grafy wariantów generacji to pakiety `suggest_<wariant>` — nazwa wariantu to reszta nazwy.
VARIANT_PREFIX = "suggest_"


def variant_graphs() -> dict[str, ModuleType]:
    """
    Description:
    Rejestr wariantów generacji, zbierany z katalogów grafów: każdy pakiet `app/graph/suggest_*`
    to jeden guzik. Nowy wariant to nowy katalog — router `/suggest` ani `GET /variants` się nie
    zmieniają (CLAUDE.md -> „Warianty generacji").

    Example args:
        (brak)

    Example result:
        {"handoff": <module app.graph.suggest_handoff>, "questions": …, "solution": …}
    """
    names = [
        module.name
        for module in pkgutil.iter_modules(app.graph.__path__)
        if module.ispkg and module.name.startswith(VARIANT_PREFIX)
    ]

    variants = {
        name.removeprefix(VARIANT_PREFIX): importlib.import_module(f"app.graph.{name}")
        for name in names
    }

    return variants
