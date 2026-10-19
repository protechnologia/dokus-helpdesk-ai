from pydantic import BaseModel, ConfigDict


class LLMAnswer(BaseModel):
    """
    Description:
    Odpowiedź modelu na jedno wywołanie: surowa treść i to, czy limit tokenów ją uciął. Ucięta
    odpowiedź w schemacie JSON to niepełny JSON, więc wołający musi to wiedzieć, zanim ją
    przeczyta (`answer_items()`). Treść niesie fragmenty tekstu zgłoszenia, więc nie trafia do
    logów.
    """

    model_config = ConfigDict(frozen=True)

    content:           str    # np. '{"dane": [{"tekst": "Leszek", "rodzaj": "IMIĘ"}]}'
    truncated:         bool   # np. False — `finish_reason` równe "length"
    prompt_tokens:     int    # np. 1840
    completion_tokens: int    # np. 32
    latency_ms:        float  # np. 2140.5
