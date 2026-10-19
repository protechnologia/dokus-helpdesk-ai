from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    """
    Description:
    Jedna wiadomość rozmowy wysyłanej do modelu: przykład z promptu (tura użytkownika i odpowiedź
    modelu) albo właściwy tekst do przejrzenia. Prompt systemowy idzie osobno, argumentem klienta.
    """

    model_config = ConfigDict(frozen=True)

    role:    Literal["user", "assistant"]  # np. "user"
    content: str                           # np. "===\nOd: Leszek Dudziak…\n==="
