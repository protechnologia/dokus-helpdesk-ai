from pydantic import BaseModel, ConfigDict, Field

from app.engine_llm.models.completion import LLMCompletion


class LLMUsage(BaseModel):
    """
    Description:
    Zużycie modelu w jednym przebiegu grafu: ile razy był wołany, ile tokenów każdej klasy
    przeszło i ile to kosztowało.

    Do czego:
    Suma rozliczeń z kolejnych wywołań modelu (`LLMCompletion`). Węzeł `agent` dokłada zużycie
    swojej tury do stanu grafu, a trasa oddaje sumę w odpowiedzi — wołający widzi, ile kosztowała
    jedna sprawa, bez sięgania do logów.

    Flow:
        1. `from_completion()` robi zużycie jednego wywołania z odpowiedzi modelu.
        2. `plus()` sumuje dwa zużycia; reduktor stanu grafu woła ją po każdej turze.

    Cztery klasy tokenów zostają osobno, jak w `LLMCompletion`: odczyt z cache kosztuje ułamek
    świeżego wejścia, a zapis więcej, więc jedna liczba „tokeny wejścia" nie pozwoliłaby
    sprawdzić kosztu. Koszt liczy klient dostawcy, tutaj jest tylko sumowany.
    """

    model_config = ConfigDict(extra="forbid")

    calls:              int   = Field(default=0, ge=0, examples=[3])
    prompt_tokens:      int   = Field(default=0, ge=0, examples=[18200])
    completion_tokens:  int   = Field(default=0, ge=0, examples=[940])
    cache_write_tokens: int   = Field(default=0, ge=0, examples=[0])
    cache_read_tokens:  int   = Field(default=0, ge=0, examples=[0])
    cost_usd:           float = Field(default=0.0, ge=0.0, examples=[0.0916])

    @classmethod
    def from_completion(
        cls,
        completion: LLMCompletion,  # np. LLMCompletion(prompt_tokens=4820, cost_usd=0.0064, …)
    ) -> "LLMUsage":
        """
        Description:
        Zużycie jednego wywołania modelu, przepisane z jego odpowiedzi.

        Example args:
            completion=LLMCompletion(text="…", model="claude-opus-5-5", prompt_tokens=4820,
                                     completion_tokens=640, latency_ms=3120.4, cost_usd=0.0321)

        Example result:
            LLMUsage(calls=1, prompt_tokens=4820, completion_tokens=640, cost_usd=0.0321)
        """
        usage = cls(
            calls              = 1,
            prompt_tokens      = completion.prompt_tokens,
            completion_tokens  = completion.completion_tokens,
            cache_write_tokens = completion.cache_write_tokens,
            cache_read_tokens  = completion.cache_read_tokens,
            cost_usd           = completion.cost_usd,
        )

        return usage

    def plus(
        self,
        other: "LLMUsage",  # np. LLMUsage(calls=1, prompt_tokens=5100, cost_usd=0.0214)
    ) -> "LLMUsage":
        """
        Description:
        Suma dwóch zużyć, pole po polu.

        Example args:
            other=LLMUsage(calls=1, prompt_tokens=5100, completion_tokens=80, cost_usd=0.0214)

        Example result:
            LLMUsage(calls=2, prompt_tokens=9920, completion_tokens=720, cost_usd=0.0535)
        """
        total = LLMUsage(
            calls              = self.calls              + other.calls,
            prompt_tokens      = self.prompt_tokens      + other.prompt_tokens,
            completion_tokens  = self.completion_tokens  + other.completion_tokens,
            cache_write_tokens = self.cache_write_tokens + other.cache_write_tokens,
            cache_read_tokens  = self.cache_read_tokens  + other.cache_read_tokens,
            cost_usd           = self.cost_usd           + other.cost_usd,
        )

        return total
