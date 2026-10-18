from anonymizer_app.engine.base import Engine

# Nazwa atrapy w każdej odpowiedzi. To samo słowo co atrapy modelu i embeddera: w całym projekcie
# znaczy „domyślne offline, nic prawdziwego pod spodem". `api` porównuje z nią nazwę silnika
# z odpowiedzi, więc jej zmiana to zmiana kontraktu między usługami.
FAKE_ENGINE_NAME = "fake"


class FakeEngine(Engine):
    """
    Description:
    Domyślny silnik (`ANONYMIZATION_ENGINE=fake`) i ten, na którym chodzą testy: oddaje tekst BEZ
    ZMIAN. Służy temu, żeby usługa stała i dała się sprawdzić, zanim powstanie prawdziwy silnik
    (p. 19.5). Niczego nie anonimizuje, więc `api` nie przepuści jego wyniku do prawdziwego
    modelu — rozpoznaje go po nazwie w odpowiedzi.

    Flow:
        1. Fabryka buduje go bez argumentów.
        2. `anonymize()` zapisuje wywołanie i oddaje tekst bez zmian.
    """

    @property
    def name(self) -> str:
        """
        Description:
        Nazwa atrapy, po której `api` ją rozpoznaje.

        Example args:
            (brak)

        Example result:
            "fake"
        """
        return FAKE_ENGINE_NAME

    async def anonymize(
        self,
        text: str,  # np. "Jan Nowak zgłasza, że przesyłki nie przychodzą."
    ) -> str:
        """
        Description:
        Oddaje tekst bez zmian i zapisuje wywołanie.

        Example args:
            text="Jan Nowak zgłasza, że przesyłki nie przychodzą."

        Example result:
            "Jan Nowak zgłasza, że przesyłki nie przychodzą."
        """
        self._log_call(text, text)

        return text
