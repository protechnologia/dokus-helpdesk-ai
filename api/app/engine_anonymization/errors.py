class AnonymizationError(Exception):
    """
    Description:
    Anonimizacja się nie udała. Zatrzymuje graf: tekst, którego nie da się bezpiecznie
    zanonimizować, nie idzie do modelu wcale (fail-closed).
    """


class AnonymizationConfigError(AnonymizationError):
    """
    Description:
    Konfiguracja nie pozwala anonimizować. Przy budowie klienta: pusty `ANONYMIZATION_BASE_URL`.
    Przy pierwszym wywołaniu: usługa `anonymizer` działa na atrapie silnika, a wołającym jest
    prawdziwy model — wtedy także w środku żądania, bo który silnik działa, wie dopiero usługa.
    Czekanie tego nie naprawi, więc handler w `api` nie zamienia go na 503.
    """
