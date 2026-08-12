from pydantic import BaseModel, Field


class RawComment(BaseModel):
    """
    Description:
    One comment of a source thread, already stripped of HTML. `kind` and `role` are carried into
    the prompt as CONTEXT, never as a verdict: the prompt itself tells the model not to trust
    them, because in this corpus a comment typed `rozwiazanie` is sometimes a question and the
    real resolution sometimes sits in an unlabelled one (CLAUDE.md -> "Pułapki tej bazy").
    """

    kind:       str = Field(examples=["rozwiazanie", "zwyczajny"])
    role:       str = Field(examples=["konsultant", "klient"])
    created_at: str = Field(examples=["2026-06-23 12:01:21"])
    body:       str = Field(examples=["Wygenerowano certyfikat z właściwym uprawnieniem."])
