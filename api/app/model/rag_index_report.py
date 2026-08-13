from pydantic import BaseModel, Field

from app.model.filter_quality_report import QualityReport


class IndexBuildReport(BaseModel):
    """
    Description:
    What one indexing run did: how many artifacts it read, how many the quality filter dropped and
    why, and how many points reached Qdrant.

    Do czego:
    An indexing run is the one moment the corpus is looked at as a whole, so it has to say what it
    threw away — a filter that silently halves the index is indistinguishable from one that works
    (CLAUDE.md -> stage 4.2). The per-reason breakdown lives in the embedded `QualityReport`; this
    model adds what happened around it.

    `read` counts artifacts that parsed cleanly, not files on disk: invalid files are reported
    separately by `helpdesk tickets validate`, and mixing the two counts would hide a broken
    artifact behind a filter statistic.
    """

    read:     int           = Field(examples=[200])
    indexed:  int           = Field(examples=[171])
    filtered: QualityReport = Field(default_factory=QualityReport)
    # Non-fatal observations the run wants the operator to see — today the drop-rate check, which
    # is how a filter gone silent announces itself (see `filter_ticket_quality.drop_rate_warning`).
    warnings: list[str]     = Field(default_factory=list)

    @property
    def dropped(self) -> int:
        """
        Description:
        How many artifacts the filter rejected.

        Example args:
            (none)

        Example result:
            29
        """
        return len(self.filtered.dropped)
