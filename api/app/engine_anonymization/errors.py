class AnonymizationError(Exception):
    """
    Description:
    Anonimizacja się nie udała. Zatrzymuje graf: tekst, którego nie da się bezpiecznie
    zanonimizować, nie idzie do modelu wcale (fail-closed).
    """


class AnonymizationConfigError(AnonymizationError):
    """
    Description:
    Konfiguracja nie pozwala zbudować anonimizatora — zgłaszane przy starcie, nie w środku
    żądania. Dziś: atrapa przy prawdziwym dostawcy LLM.
    """
