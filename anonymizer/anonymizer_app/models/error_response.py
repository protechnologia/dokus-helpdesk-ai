from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Description:
    Jeden kształt błędu dla każdej obsłużonej awarii, ten sam co w `api` — wołającym jest właśnie
    `api`, więc jeden kształt to jedna obsługa po tamtej stronie. Nigdy nie cytuje tekstu, który
    przyszedł do anonimizacji.
    """

    detail:     str        = Field(examples=["Anonymization failed"])
    request_id: str | None = Field(default=None, examples=["6f1c…"])
