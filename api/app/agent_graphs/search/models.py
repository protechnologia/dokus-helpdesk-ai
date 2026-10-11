from pydantic import BaseModel, ConfigDict, Field


class SearchNotes(BaseModel):
    """
    Description:
    Argumenty `respond_search` i wynik grafu `search`: uwagi dla wdrożeniowca o tym, co agent
    znalazł.

    Do czego:
    Sama lista źródeł nie mówi tego, od czego zależy następny krok człowieka: trzy sprawy o jednym
    objawie i trzech przyczynach wyglądają na niej tak samo jak trzy zgodne. Uwagi mówią, czy
    przeczytane sprawy zgadzają się co do przyczyny, co mówią instrukcje i kod, czego agent szukał
    bez skutku i co w kodzie wykluczył. Wdrożeniowiec decyduje na ich podstawie, czy dopytać
    klienta, odpowiedzieć, czy przekazać sprawę; uwagi tej decyzji nie podpowiadają.

    Kształt uwag trzyma prompt systemowy grafu: lekki Markdown, cztery sekcje z nagłówkiem `##`,
    w sekcji punkt na sprawę, sekcję instrukcji albo fragment kodu. Kod tego kształtu nie
    sprawdza.

    Źródeł tu nie ma z założenia: lista źródeł powstaje z `cite()` narzędzi i leży w `sources`
    stanu grafu, nigdy z tego, co model zadeklarował (zasada 9). Uwagi są wymagane i niepuste,
    inaczej niż w propozycjach: także przy zerze trafień jest co napisać — czego agent szukał.
    """

    model_config = ConfigDict(extra="forbid")

    internal_notes: str = Field(min_length=1, examples=["## Zgłoszenia historyczne\n- 41002: …"])
