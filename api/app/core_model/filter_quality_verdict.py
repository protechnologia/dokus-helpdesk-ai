from pydantic import BaseModel, Field


class RuleHit(BaseModel):
    """
    Description:
    One rule firing on one record: which rule, and the fragment that triggered it.

    The fragment is the point. Tuning a threshold or a pattern against 200 records is guesswork
    unless the report says WHAT the rule read — "solution is empty" is a claim, "solution starts
    with 'Brak rozstrzygnięcia w wątku'" is evidence.
    """

    rule:     str = Field(examples=["no_resolution_stated"])
    evidence: str = Field(examples=["Brak rozstrzygnięcia w wątku."])


class QualityVerdict(BaseModel):
    """
    Description:
    What the quality filter concluded about one artifact: keep it or drop it, and why.

    Not a boolean, deliberately. The filter has to report what it rejects (CLAUDE.md -> stage 4.2),
    because the corpus is small enough that every drop is worth reviewing, and because a rule that
    rejects the wrong records is invisible in an aggregate count. A record may trip several rules;
    all of them are kept, since the first one alphabetically is not necessarily the interesting one.
    """

    ticket_id: str           = Field(examples=["33644"])
    hits:      list[RuleHit] = Field(default_factory=list)

    @property
    def keep(self) -> bool:
        """
        Description:
        Tells whether the record goes into the index. No rule fired means keep — the filter drops
        what it can name a reason for, never what it merely fails to recognise.

        Example args:
            (none)

        Example result:
            True
        """
        return not self.hits

    @property
    def reasons(self) -> list[str]:
        """
        Description:
        Names of the rules that fired, for grouping in the report.

        Example args:
            (none)

        Example result:
            ["no_resolution_stated"]
        """
        return [hit.rule for hit in self.hits]
