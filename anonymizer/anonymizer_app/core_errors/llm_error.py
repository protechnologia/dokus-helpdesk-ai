from anonymizer_app.core_errors.engine_error import EngineError


class LLMError(EngineError):
    """
    Description:
    Awaria wywołania modelu anonimizującego w trakcie żądania: model nie odpowiedział w czasie,
    był nieosiągalny, odpowiedział błędem albo czymś, czego nie da się przeczytać. Dziedziczy po
    `EngineError`, więc trasa oddaje 503, a graf w `api` staje (fail-closed) — tekst bez węzła osób
    nie może pójść dalej. Komunikat nigdy nie cytuje tekstu ani odpowiedzi modelu.
    """
