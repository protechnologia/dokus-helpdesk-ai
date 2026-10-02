from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolCall(BaseModel):
    """
    Description:
    Jedno wywołanie narzędzia, o które poprosił model: którego, z jakimi argumentami i pod jakim
    id. Po tym id wynik narzędzia wraca do modelu jako wiadomość `tool`.

    Argumenty to surowy JSON od modelu — waliduje je dopiero `query_model` narzędzia, bo tylko
    ono wie, jakie są poprawne.
    """

    model_config = ConfigDict(extra="forbid")

    call_id:   str            = Field(min_length=1, examples=["call_1"])
    name:      str            = Field(min_length=1, examples=["find_tickets"])
    arguments: dict[str, Any] = Field(default_factory=dict, examples=[{"problem": "…"}])


class ChatMessage(BaseModel):
    """
    Description:
    Jedna wiadomość rozmowy z modelem w pętli agenta: zgłoszenie (`user`), odpowiedź modelu
    (`assistant`, czasem z wywołaniami narzędzi) albo wynik narzędzia (`tool`).

    Do czego:
    Własny typ zamiast wiadomości LangChaina: pętla rozmawia z modelem przez `LLMClient`
    (zasada 4), a format wiadomości u konkretnego dostawcy tłumaczy jego klient (CLAUDE.md ->
    „Plan i TODO", p. 14). LangGraph nie wymaga typów LangChaina, więc stan grafu nie musi ich
    znać. Prompt systemowy nie jest wiadomością — dokłada go węzeł `agent` przy każdej turze.
    """

    model_config = ConfigDict(extra="forbid")

    role:       Literal["user", "assistant", "tool"]
    content:    str            = Field(default="", examples=["Znalezione zgłoszenia: 3 …"])
    tool_calls: list[ToolCall] = Field(default_factory=list)
    call_id:    str | None     = Field(default=None, examples=["call_1"])

    @model_validator(mode="after")
    def check_tool_links(self) -> "ChatMessage":
        """
        Description:
        Pilnuje powiązań z narzędziami: wynik narzędzia musi wskazywać wywołanie, na które
        odpowiada, a wywołania narzędzi zleca wyłącznie model. Dostawcy odrzucają rozmowę
        z zerwanym powiązaniem, więc błąd ma wyjść tutaj, a nie w środku pętli.

        Example args:
            (brak)

        Example result:
            ChatMessage(role="tool", content="…", call_id="call_1")

        Raises:
            ValueError: wiadomość `tool` bez `call_id` albo wywołania narzędzi spoza `assistant`
        """
        if self.role == "tool" and not self.call_id:
            raise ValueError("wiadomość tool musi wskazywać call_id wywołania")

        if self.tool_calls and self.role != "assistant":
            raise ValueError("wywołania narzędzi może zawierać tylko wiadomość assistant")

        return self
