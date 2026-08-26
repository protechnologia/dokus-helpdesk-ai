from pydantic import BaseModel, ConfigDict, Field


class GenerationVariant(BaseModel):
    """
    Description:
    One kind of proposal the operator can ask for — one button in the helpdesk UI. `name` is what
    `POST /suggest` accepts as its `variant` parameter, `label` is what the button says, and
    `prompt` is the instruction the generation service hands the model.

    Do czego:
    The unit of configurability in stage 6. Code never names a variant: it asks the store for the
    set, looks one up by name and generates with its prompt, so a customer adding a fourth button
    touches data and not our source (CLAUDE.md -> "Generacja propozycji").

    `requires_hits` is the one field with teeth. It says whether the variant has anything to stand
    on with an EMPTY index: `questions` and `handoff` are useful on day one, while `solution`
    without hits would have to invent its content, which rule 9 forbids. A variant that requires
    hits and gets none returns an empty source list rather than a generated answer.

    `prompt` is TEXT here, not a filename, even though the bundled default set stores it as a
    markdown document beside this code. Resolving the file belongs to the loader that owns that
    file format; keeping text in the contract is what lets stage 8 serve the same variant out of a
    SQL column without the service or this model changing (CLAUDE.md -> stage 8).
    """

    # A key we do not recognise means the store drifted from this contract — surface it at load
    # time rather than dropping a field the customer thought they had configured.
    model_config = ConfigDict(extra="forbid")

    name:          str  = Field(examples=["questions"])
    label:         str  = Field(examples=["Jakie pytania zadać"])
    requires_hits: bool = Field(examples=[False])
    prompt:        str  = Field(examples=["Jesteś asystentem wdrożeniowca helpdesku…"])
