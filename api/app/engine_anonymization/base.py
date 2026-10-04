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
        Zamienia dane osobowe i sekrety w tekście na pseudonimy.

        Example args:
            text="Jan Kowalski zgłasza, że przesyłki nie przychodzą."

        Example result:
            AnonymizedText(text="{KLIENT_1} zgłasza, że przesyłki nie przychodzą.")

        Raises:
            AnonymizationError: tekstu nie da się bezpiecznie zanonimizować
        """
