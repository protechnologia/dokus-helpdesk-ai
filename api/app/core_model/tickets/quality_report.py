from collections import Counter

from pydantic import BaseModel, Field

from app.core_model.tickets.quality_verdict import QualityVerdict


class QualityReport(BaseModel):
    """
    Description:
    Wynik filtrowania całego korpusu: każdy werdykt i rozbicie, które przebieg ma wypisać.

    Flow:
        1. Filtr ocenia każdy artefakt i dopisuje jego `QualityVerdict`.
        2. `kept` i `dropped` dzielą werdykty, `by_reason` liczy odrzucenia per reguła.
        3. Wołający (komenda `helpdesk tickets index`) wypisuje rozbicie i decyduje, co indeksować —
           serwis raportuje, nie wypisuje i nie indeksuje.

    Liczby per powód zamiast jednej sumy, bo reguła, która odrzuca nie te rekordy, jest w jednej
    liczbie niewidoczna.
    """

    verdicts: list[QualityVerdict] = Field(default_factory=list)

    @property
    def kept(self) -> list[QualityVerdict]:
        """
        Description:
        Werdykty rekordów, które idą do indeksu, w kolejności czytania.

        Example args:
            (brak)

        Example result:
            [QualityVerdict(ticket_id="33644", hits=[])]
        """
        return [verdict for verdict in self.verdicts if verdict.keep]

    @property
    def dropped(self) -> list[QualityVerdict]:
        """
        Description:
        Werdykty rekordów odrzuconych, każdy z regułami, które zadziałały.

        Example args:
            (brak)

        Example result:
            [QualityVerdict(ticket_id="19596", hits=[RuleHit(rule="no_resolution", …)])]
        """
        return [verdict for verdict in self.verdicts if not verdict.keep]

    def by_reason(self) -> dict[str, int]:
        """
        Description:
        Liczy odrzucenia per reguła, od najczęstszej. Rekord, który uruchomił dwie reguły, liczy
        się w obu — pytanie brzmi „ile odrzuca każda reguła", a nie „ile rekordów wpadło do
        którego koszyka".

        Example args:
            (brak)

        Example result:
            {"no_resolution": 29}
        """
        counter = Counter(rule for verdict in self.dropped for rule in verdict.reasons)

        return dict(counter.most_common())

    def ticket_ids_for(
        self,
        rule: str,  # np. "no_resolution"
    ) -> list[str]:
        """
        Description:
        Numery zgłoszeń odrzuconych przez jedną regułę. Raport komendy wypisuje je pod liczbą,
        żeby odsetek odrzuceń dało się sprawdzić na konkretnych zgłoszeniach.

        Example args:
            rule="no_resolution"

        Example result:
            ["19596", "30423"]
        """
        return [verdict.ticket_id for verdict in self.dropped if rule in verdict.reasons]
