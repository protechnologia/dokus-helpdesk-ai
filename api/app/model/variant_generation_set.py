from pydantic import BaseModel, Field, model_validator

from app.model.variant_generation import GenerationVariant


class GenerationVariantSet(BaseModel):
    """
    Description:
    The configurable set of generation variants, plus the version it was loaded at.

    Why versioned: the same reason the outcome vocabulary is (CLAUDE.md -> "Prompty"). Editing a
    variant changes what a button produces, and "why did yesterday's proposal read differently"
    has to be answerable — in stage 8 an audited verdict records the version it was issued under.
    Unlike the parsing vocabulary this version does not invalidate anything on disk: proposals are
    generated fresh each time, so no stored artifact depends on it.

    Deliberately NOT an Enum in code: which buttons a helpdesk wants over a ticket is a statement
    about how that organisation answers customers, so the set belongs to the customer's data. The
    loader that reads it is the seam stage 8 swaps for SQL.
    """

    version:  int                    = Field(examples=[1])
    variants: list[GenerationVariant]

    @model_validator(mode="after")
    def _names_must_be_unique(self) -> "GenerationVariantSet":
        """
        Description:
        Rejects a set with two variants under one name. `get()` would return the first and the
        second would be unreachable — a button drawn by the helpdesk that generates someone else's
        prompt, with nothing anywhere to say so. A config error has to be loud at load time.

        Example args:
            (none — runs on every constructed set)

        Example result:
            self, unchanged

        Raises:
            ValueError: two or more variants share a name
        """
        names = self.names()

        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"warianty o powtórzonej nazwie: {', '.join(duplicates)}")

        return self

    def names(self) -> list[str]:
        """
        Description:
        Returns just the identifiers, in declared order — what `POST /suggest` validates its
        `variant` parameter against and what the CLI lists.

        Example args:
            (none)

        Example result:
            ["questions", "solution", "handoff"]
        """
        return [variant.name for variant in self.variants]

    def get(
        self,
        name: str,  # e.g. "questions"
    ) -> GenerationVariant | None:
        """
        Description:
        Finds one variant by name, or None when the set has no such button.

        None rather than an exception, because the caller decides what the miss means: the HTTP
        handler turns it into 422 (a typo in the helpdesk UI must be visible at once, never a
        silent fallback to a default variant), while the CLI prints the available names.

        Example args:
            name="questions"

        Example result:
            GenerationVariant(name="questions", label="Jakie pytania zadać", requires_hits=False, …)
        """
        return next((variant for variant in self.variants if variant.name == name), None)
