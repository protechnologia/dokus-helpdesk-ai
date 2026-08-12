from pydantic import BaseModel, Field

from app.model.dict_resolution_class import ResolutionClass


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
    source. The loader that reads it stays in `rules/`, which is the seam stage 8 swaps for SQL.
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
