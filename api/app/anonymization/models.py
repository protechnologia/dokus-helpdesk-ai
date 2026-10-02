from pydantic import BaseModel, ConfigDict, Field


class AnonymizedText(BaseModel):
    """
    Description:
    Tekst po anonimizacji — jedyna postać treści zgłoszenia, która może trafić do modelu
    zewnętrznego. Osobny typ, a nie zwykły `str`, żeby granica była widoczna w sygnaturach: kod
    przyjmujący `AnonymizedText` nie przyjmie surowego tekstu przez pomyłkę.

    Tworzy go wyłącznie anonimizator — atrapa w p. 4, usługa w p. 19 (CLAUDE.md -> „Plan i TODO").
    Python tego nie wymusi; pilnuje tego test grafów (p. 12). Mapowanie pseudonimów na dane
    dochodzi razem z prawdziwym anonimizatorem.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, examples=["{KLIENT_1} zgłasza, że przesyłki nie przychodzą."])
