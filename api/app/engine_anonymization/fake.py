from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.models import AnonymizedText


class FakeAnonymizer(Anonymizer):
    """
    Description:
    Atrapa anonimizatora do testów: oddaje tekst BEZ ZMIAN, opakowany w `AnonymizedText`, bez
    usługi `anonymizer`. W czasie działania `api` jej nie używa — `build_anonymizer` buduje
    zawsze klienta usługi, a o atrapie silnika decyduje konfiguracja usługi. Niczego nie
    anonimizuje, więc wolno jej używać wyłącznie z atrapą modelu albo na zmyślonych danych.

    Flow:
        1. Każde `anonymize()` zapisuje tekst w `texts` i zwraca go bez zmian.
    """

    def __init__(self):
        """
        Description:
        Zakłada dziennik anonimizowanych tekstów.

        Example args:
            (brak)

        Example result:
            FakeAnonymizer z pustym `texts`
        """
        # Publiczne celowo: testy sprawdzają, co przeszło przez anonimizację.
        self.texts: list[str] = []

    async def anonymize(
        self,
        text: str,  # np. "Nie przychodzą przesyłki z e-Doręczeń"
    ) -> AnonymizedText:
        """
        Description:
        Zapisuje tekst i zwraca go bez zmian.

        Example args:
            text="Nie przychodzą przesyłki z e-Doręczeń"

        Example result:
            AnonymizedText(text="Nie przychodzą przesyłki z e-Doręczeń")
        """
        self.texts.append(text)

        return AnonymizedText(text=text)
