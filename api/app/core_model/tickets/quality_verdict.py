from pydantic import BaseModel, Field


class RuleHit(BaseModel):
    """
    Description:
    Jedno zadziałanie reguły na jednym rekordzie: która reguła i fragment, który ją uruchomił.

    Fragment jest tu najważniejszy. Strojenie progu albo wzorca na 200 rekordach to zgadywanie,
    dopóki raport nie mówi, CO reguła przeczytała — „solution jest puste" to twierdzenie,
    „solution zaczyna się od »Brak rozstrzygnięcia w wątku«" to dowód.
    """

    rule:     str = Field(examples=["no_resolution"])
    evidence: str = Field(examples=["Brak rozstrzygnięcia w wątku."])


class QualityVerdict(BaseModel):
    """
    Description:
    Co filtr jakości uznał o jednym artefakcie: zostawić czy odrzucić, i dlaczego.

    Celowo nie wartość logiczna. Filtr ma raportować, co odrzuca (CLAUDE.md -> „Domena: kontrakt
    sparsowanego zgłoszenia"): korpus jest na tyle mały, że każde odrzucenie warto obejrzeć,
    a reguła, która odrzuca nie te rekordy, jest w samej liczbie niewidoczna. Rekord może
    uruchomić kilka reguł; zostają wszystkie, bo pierwsza z nich nie musi być tą istotną.
    """

    ticket_id: str           = Field(examples=["33644"])
    hits:      list[RuleHit] = Field(default_factory=list)

    @property
    def keep(self) -> bool:
        """
        Description:
        Mówi, czy rekord idzie do indeksu. Gdy żadna reguła nie zadziałała, zostaje: filtr
        odrzuca to, dla czego umie nazwać powód, nigdy to, czego po prostu nie rozpoznał.

        Example args:
            (brak)

        Example result:
            True
        """
        return not self.hits

    @property
    def reasons(self) -> list[str]:
        """
        Description:
        Nazwy reguł, które zadziałały — do grupowania w raporcie.

        Example args:
            (brak)

        Example result:
            ["no_resolution"]
        """
        return [hit.rule for hit in self.hits]
