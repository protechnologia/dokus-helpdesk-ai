from pydantic import BaseModel, ConfigDict, Field


class AnonymizedText(BaseModel):
    """
    Description:
    Tekst po anonimizacji — jedyna postać treści zgłoszenia, która może trafić do modelu
    zewnętrznego. Osobny typ, a nie zwykły `str`, żeby granica była widoczna w sygnaturach: kod
    przyjmujący `AnonymizedText` nie przyjmie surowego tekstu przez pomyłkę.

    Tworzy go wyłącznie anonimizator — atrapa w p. 4, usługa w p. 19 (CLAUDE.md -> „Plan").
    Python tego nie wymusi; pilnuje tego test grafów (p. 12). Mapowania znaczników na dane nie
    ma: po anonimizacji wszystko działa na znacznikach (CLAUDE.md -> „Świadomie pominięte").
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, examples=["{IMIĘ} {NAZWISKO} zgłasza brak przesyłek."])


class AnonymizerInfo(BaseModel):
    """
    Description:
    Co wiadomo o anonimizatorze bez anonimizowania czegokolwiek: czy usługa odpowiada, którym
    silnikiem działa i z jakim modelem. Oddaje go `Anonymizer.describe()`, a trasa
    `GET /instance` podaje dalej, żeby front pokazał, co anonimizuje zgłoszenia.

    Niedostępna usługa to wartość (`available=False`, bez silnika i modelu), nie błąd: opis
    instancji ma pokazać, że anonimizatora nie ma, zamiast nie powiedzieć nic.
    """

    model_config = ConfigDict(extra="forbid")

    available: bool       = Field(examples=[True])
    # Nazwa silnika usługi: „agent" albo „fake"; `None`, gdy usługa nie odpowiedziała.
    engine:    str | None = Field(examples=["agent"])
    # Model anonimizujący silnika `agent`; `None` przy atrapie silnika i przy braku odpowiedzi.
    model:     str | None = Field(examples=["speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic"])
