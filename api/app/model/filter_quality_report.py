from collections import Counter

from pydantic import BaseModel, Field

from app.model.filter_quality_verdict import QualityVerdict


class QualityReport(BaseModel):
    """
    Description:
    Result of filtering a whole corpus: every verdict, plus the breakdown the run has to print.

    Flow:
        1. The filter evaluates each artifact and appends its `QualityVerdict`.
        2. `kept` / `dropped` split them; `by_reason` counts drops per rule.
        3. The caller (stage 4.4's CLI) prints the breakdown and decides what to index — the
           service reports, it does not print and does not index.

    Why per-reason counts rather than a total: a rule that fires on the wrong records is invisible
    in a single number, and one reason — `multi_topic` — is not a quality judgement at all. Those
    records are the richest in the corpus and get dropped only because they do not fit the "one
    ticket, one record" contract; their count is an input to the stage 11 decision, so it must not
    dissolve into a sum (CLAUDE.md -> stage 4.2).
    """

    verdicts: list[QualityVerdict] = Field(default_factory=list)

    @property
    def kept(self) -> list[QualityVerdict]:
        """
        Description:
        Verdicts of the records that go into the index, in the order they were read.

        Example args:
            (none)

        Example result:
            [QualityVerdict(ticket_id="33644", hits=[])]
        """
        return [verdict for verdict in self.verdicts if verdict.keep]

    @property
    def dropped(self) -> list[QualityVerdict]:
        """
        Description:
        Verdicts of the rejected records, each carrying the rules that fired.

        Example args:
            (none)

        Example result:
            [QualityVerdict(ticket_id="19596", hits=[RuleHit(rule="no_resolution_stated", …)])]
        """
        return [verdict for verdict in self.verdicts if not verdict.keep]

    def by_reason(self) -> dict[str, int]:
        """
        Description:
        Counts drops per rule, most frequent first. A record tripping two rules counts under both —
        the question this answers is "how much does each rule reject", not "how many records fell
        into which bucket".

        Example args:
            (none)

        Example result:
            {"no_resolution_stated": 29, "no_resolution_admitted": 11, "multi_topic": 1}
        """
        counter = Counter(rule for verdict in self.dropped for rule in verdict.reasons)

        return dict(counter.most_common())

    def ticket_ids_for(
        self,
        rule: str,  # e.g. "multi_topic"
    ) -> list[str]:
        """
        Description:
        Ticket ids dropped by one named rule. Exists for `multi_topic`, whose count alone is not
        enough: stage 11 decides whether to split those tickets into several records, and that
        decision needs the tickets themselves, not a number.

        Example args:
            rule="multi_topic"

        Example result:
            ["30423"]
        """
        return [verdict.ticket_id for verdict in self.dropped if rule in verdict.reasons]
