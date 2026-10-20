from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.client import FAKE_ENGINE
from app.engine_anonymization.models import AnonymizedText, AnonymizerInfo


class FakeAnonymizer(Anonymizer):
    """
    Description:
    Atrapa anonimizatora do testów: oddaje tekst BEZ ZMIAN, opakowany w `AnonymizedText`, bez
    usługi `anonymizer`. W czasie działania `api` jej nie używa — `build_anonymizer` buduje
    zawsze klienta usługi, a o atrapie silnika decyduje konfiguracja usługi. Niczego nie
    anonimizuje, więc wolno jej używać wyłącznie z atrapą modelu albo na zmyślonych danych.

    Flow:
        1. Każde `anonymize()` zapisuje tekst w `texts` i zwraca go bez zmian.
        2. `describe()` przedstawia się jak atrapa silnika usługi: silnik „fake", bez modelu.
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

    async def describe(self) -> AnonymizerInfo:
        """
        Description:
        Przedstawia atrapę tak, jak usługa przedstawia swoją atrapę silnika: dostępna, silnik
        „fake", bez modelu.

        Example args:
            (brak)

        Example result:
            AnonymizerInfo(available=True, engine="fake", model=None)
        """
        info = AnonymizerInfo(available=True, engine=FAKE_ENGINE, model=None)

        return info
