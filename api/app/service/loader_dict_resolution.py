from functools import lru_cache
from pathlib import Path

from app.model.dict_resolution_vocabulary import ResolutionVocabulary

# The bundled default set. Stage 8 replaces this SOURCE with the SQL rules store, and this
# function is the seam that makes the swap invisible: every caller asks for the vocabulary here,
# so none of them learns where it came from (CLAUDE.md -> "Bramki jakości": the same route the
# `Popraw` style rules and the generation variants take). There is no `rules/` package any more —
# the seam is this function, and stage 8 adds `loader_*` siblings next to it rather than a folder.
DEFAULT_DICT_FILE = Path(__file__).parent.parent / "text" / "dict_resolution.json"


@lru_cache
def get_resolution_classes(path: Path = DEFAULT_DICT_FILE) -> ResolutionVocabulary:
    """
    Description:
    Loads the outcome vocabulary. Cached per path rather than read at import time, so importing
    the module touches no disk and a test can point at its own file.

    Example args:
        path=Path("/code/app/text/dict_resolution.json")

    Example result:
        ResolutionVocabulary(version=1, classes=[ResolutionClass(name="naprawione", …), …])

    Raises:
        FileNotFoundError: the vocabulary file is missing — a deployment error, not a runtime one
    """
    return ResolutionVocabulary.model_validate_json(path.read_text(encoding="utf-8"))
