from pydantic import BaseModel, ConfigDict, Field


class GenerationVariant(BaseModel):
    """
    Description:
    One kind of proposal the operator can ask for — one button in the helpdesk UI. `name` is what
    `POST /suggest` accepts as its `variant` parameter, `label` is what the button says, and the
    two prompts are what the generation service hands the model.

    Do czego:
    The unit of configurability in stage 6. Code never names a variant: it asks the store for the
    set, looks one up by name and generates with its prompt, so a customer adding a fourth button
    touches data and not our source (CLAUDE.md -> "Generacja propozycji").

    `requires_hits` is the one field with teeth. It says whether the variant has anything to stand
    on with an EMPTY index: `questions` and `handoff` are useful on day one, while `solution`
    without hits would have to invent its content, which rule 9 forbids. A variant that requires
    hits and gets none returns an empty source list rather than a generated answer.

    Split into a system and a user prompt, the same convention the parsing prompt follows: the
    role the model plays is a different kind of sentence from the instructions it carries out, and
    the provider API keeps them apart anyway. WHICH of the two a customer may edit — one, both, or
    only a delimited block inside one — is deliberately left open until stage 8, when it will be
    visible what they actually want to change.

    Both are TEXT here, not filenames, even though the bundled default set stores them as markdown
    documents beside this code. Resolving those files belongs to the loader that owns the file
    format; keeping text in the contract is what lets stage 8 serve the same variant out of SQL
    columns without the service or this model changing.
    """

    # A key we do not recognise means the store drifted from this contract — surface it at load
    # time rather than dropping a field the customer thought they had configured.
    model_config = ConfigDict(extra="forbid")

    name:          str  = Field(examples=["questions"])
    label:         str  = Field(examples=["Jakie pytania zadać"])
    requires_hits: bool = Field(examples=[False])
    system_prompt: str  = Field(examples=["Jesteś asystentem wdrożeniowca helpdesku…"])
    user_prompt:   str  = Field(examples=["Zaproponuj pytania, które warto zadać…"])
