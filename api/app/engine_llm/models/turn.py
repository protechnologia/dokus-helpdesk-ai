from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine_llm.models.messages import ChatMessage
from app.engine_llm.models.usage import LLMUsage


class LLMTurn(BaseModel):
    """
    Description:
    Jedna tura modelu w rozmowie z narzędziami: wiadomość, którą model odpowiedział, i rozliczenie
    wywołania.

    Do czego:
    Wynik `LLMClient.complete_turn()`. Węzeł `agent` dokleja `message` do rozmowy w stanie grafu,
    a `usage` oddaje do sumy zużycia przebiegu. Wywołania narzędzi są w `message` w naszym
    kształcie (`ToolCall`), niezależnie od dostawcy; to, co dostawca każe odesłać w następnej
    turze, klient zostawia w `message.provider_items`.

    Zużycie jest od razu w `LLMUsage`, a nie w polach jak w `LLMCompletion`: tura nie ma jednego
    tekstu, a jej rozliczenie idzie wprost do stanu grafu.
    """

    model_config = ConfigDict(extra="forbid")

    message:    ChatMessage                                    # tura modelu, doklejana do rozmowy
    model:      str         = Field(examples=["gpt-6.1-sol"])  # model, który odpowiedział
    latency_ms: float       = Field(examples=[3120.4])
    usage:      LLMUsage                                       # zużycie tego jednego wywołania

    @model_validator(mode="after")
    def check_message_is_a_model_turn(self) -> "LLMTurn":
        """
        Description:
        Pilnuje, że klient oddał turę modelu, a nie wiadomość innej roli: doklejona do rozmowy
        zepsułaby ją po cichu, a dostawca odrzuciłby dopiero następne żądanie.

        Example args:
            (brak)

        Example result:
            LLMTurn(message=ChatMessage(role="assistant", …), model="fake", …)

        Raises:
            ValueError: `message` ma rolę inną niż `assistant`
        """
        if self.message.role != "assistant":
            raise ValueError("tura modelu musi być wiadomością assistant")

        return self
