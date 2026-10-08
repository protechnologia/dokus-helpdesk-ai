from pydantic import BaseModel, ConfigDict, Field


class Proposal(BaseModel):
    """
    Description:
    Propozycja odpowiedzi dla wdrożeniowca — wynik grafów `suggest_*` (pytania, rozwiązanie,
    przekazanie sprawy): treść dla klienta i osobno uwagi dla wdrożeniowca.

    Do czego:
    Jeden kształt dla wszystkich wariantów, więc nowy guzik to nowy katalog grafu, a nie zmiana
    routera (CLAUDE.md -> „Warianty generacji"). Źródeł tu nie ma z założenia: lista źródeł
    powstaje z `cite()` narzędzi i leży w `sources` stanu grafu — nigdy z tego, co model
    zadeklarował (zasada 9). Wariant, którym propozycja powstała, zna wołający.

    Treść i uwagi są osobno, bo mają dwóch odbiorców: `text` ma dać się wysłać klientowi bez
    wycinania, a w `internal_notes` stoi to, co do klienta wyjść nie może — nazwy klas i ścieżki
    z kodu, notatki przy pytaniach, czego materiał nie rozstrzyga. Uwagi są wymagane, ale mogą być
    puste: model musi o nich zdecydować, a pusty napis znaczy, że uwag nie ma.
    """

    model_config = ConfigDict(extra="forbid")

    text:           str = Field(min_length=1, examples=["1. Od kiedy nie przychodzą przesyłki? …"])
    internal_notes: str = Field(examples=["1: odcina zacięcie kolejki (zgł. 41002)"])
