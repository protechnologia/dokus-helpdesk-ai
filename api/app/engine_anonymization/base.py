from abc import ABC, abstractmethod

from app.engine_anonymization.models import AnonymizedText, AnonymizerInfo


class Anonymizer(ABC):
    """
    Description:
    Jedyna droga od surowego tekstu do `AnonymizedText`. Węzeł `anonymize` dostaje anonimizator
    przez konstruktor i nie wie, czy pod spodem jest atrapa z testu, czy usługa.

    Flow:
        1. Fabryka (`build_anonymizer`) buduje klienta usługi z konfiguracji; testy podają atrapę.
        2. Węzeł `anonymize` woła `anonymize()` na `input_text` grafu.
        3. Wynik trafia do stanu; dalej model zewnętrzny widzi wyłącznie jego.
        4. `describe()` mówi, czy anonimizator odpowiada i którym silnikiem działa — dla opisu
           instancji (`GET /instance`), nie dla przebiegu grafu.
        5. `aclose()` zwalnia to, co implementacja trzyma (połączenia klienta usługi).

    Fail-closed: implementacja, która nie umie zanonimizować tekstu, zgłasza błąd — nigdy nie
    oddaje tekstu bez zmian.
    """

    @abstractmethod
    async def anonymize(
        self,
        text: str,  # np. "Jan Kowalski zgłasza, że przesyłki nie przychodzą."
    ) -> AnonymizedText:
        """
        Description:
        Zamienia dane osobowe i sekrety w tekście na znaczniki swojego rodzaju.

        Example args:
            text="Jan Kowalski zgłasza, że przesyłki nie przychodzą."

        Example result:
            AnonymizedText(text="{IMIĘ} {NAZWISKO} zgłasza, że przesyłki nie przychodzą.")

        Raises:
            AnonymizationError: tekstu nie da się bezpiecznie zanonimizować
        """

    @abstractmethod
    async def describe(self) -> AnonymizerInfo:
        """
        Description:
        Mówi, czy anonimizator odpowiada, którym silnikiem działa i z jakim modelem — bez
        anonimizowania czegokolwiek. Niedostępność to odpowiedź (`available=False`), nie błąd:
        czyta to opis instancji, a nie przebieg grafu, więc fail-closed tu nie obowiązuje.

        Example args:
            (brak)

        Example result:
            AnonymizerInfo(available=True, engine="agent",
                           model="speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic")
        """

    async def aclose(self) -> None:
        """
        Description:
        Zwalnia zasoby anonimizatora. Domyślnie nic nie robi — atrapa niczego nie trzyma;
        klient usługi zamyka tu połączenia.

        Example args:
            (brak)

        Example result:
            None
        """
        # Celowo nie abstrakcyjna: atrapa i anonimizatory pisane w testach nie mają czego zamykać.
        return None
