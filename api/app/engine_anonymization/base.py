from abc import ABC, abstractmethod

from app.engine_anonymization.models import AnonymizedText


class Anonymizer(ABC):
    """
    Description:
    Jedyna droga od surowego tekstu do `AnonymizedText`. Węzeł `anonymize` dostaje anonimizator
    przez konstruktor i nie wie, czy pod spodem jest atrapa, czy usługa.

    Flow:
        1. Fabryka (`build_anonymizer`) wybiera implementację z konfiguracji.
        2. Węzeł `anonymize` woła `anonymize()` na `input_text` grafu.
        3. Wynik trafia do stanu; dalej model zewnętrzny widzi wyłącznie jego.
        4. `aclose()` zwalnia to, co implementacja trzyma (połączenia klienta usługi).

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
