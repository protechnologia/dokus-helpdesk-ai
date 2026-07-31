from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

# The bundled default set. Stage 8 replaces this source with the SQL rules store — the point of
# reading it through `get_resolution_classes()` is that the swap must not touch a single caller
# (CLAUDE.md -> "Bramki jakości": the same route the `Popraw` style rules take).
DEFAULT_RULES_FILE = Path(__file__).with_name("resolution_classes.json")


class ResolutionClass(BaseModel):
    """
    Description:
    One kind of outcome a ticket can end with. `name` is what lands in `ParsedTicket.resolution`;
    `hint` exists for the parsing prompt, which has to tell the model what the value means —
    a bare list of identifiers gets classified by guesswork.
    """

    name: str = Field(examples=["bez_zmian_w_systemie"])
    hint: str = Field(examples=["w systemie nic nie zmieniono — klient dostał wskazówkę"])


class ResolutionVocabulary(BaseModel):
    """
    Description:
    The configurable vocabulary of outcome kinds, plus the version it was loaded at.

    Why versioned: this vocabulary is interpolated into the PARSING prompt, so editing it changes
    what future artifacts mean. Every `ParsedTicket` records the version it was produced with, so
    a later edit does not silently invalidate `data/parsed/` (CLAUDE.md -> rule 7) and re-parsing
    can be selective instead of total.

    Deliberately NOT an Enum in code: where one helpdesk draws the line between "we changed the
    system" and "the customer acts on their side" reflects how that organisation works, and means
    something different in the next one — so the set belongs to the customer's data, not to our
    source.
    """

    version: int                     = Field(examples=[1])
    classes: list[ResolutionClass]

    def names(self) -> list[str]:
        """
        Description:
        Returns just the identifiers, in declared order — what a validator compares against and
        what the prompt lists as allowed answers.

        Example args:
            (none)

        Example result:
            ["naprawione", "bez_zmian_w_systemie", "brak"]
        """
        return [entry.name for entry in self.classes]


@lru_cache
def get_resolution_classes(path: Path = DEFAULT_RULES_FILE) -> ResolutionVocabulary:
    """
    Description:
    Loads the outcome vocabulary. Cached per path rather than read at import time, so importing
    the module touches no disk and a test can point at its own file.

    Example args:
        path=Path("/code/app/rules/resolution_classes.json")

    Example result:
        ResolutionVocabulary(version=1, classes=[ResolutionClass(name="naprawione", …), …])

    Raises:
        FileNotFoundError: the vocabulary file is missing — a deployment error, not a runtime one
    """
    return ResolutionVocabulary.model_validate_json(path.read_text(encoding="utf-8"))
