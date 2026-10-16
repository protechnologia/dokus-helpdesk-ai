import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Engine(ABC):
    """
    Description:
    Jedyna droga, którą ta usługa zamienia dane w tekście na znaczniki. Nazywa się „silnik", a nie
    „anonimizator", bo `Anonymizer` to kontrakt po stronie `api`, a ta sama nazwa po obu stronach
    granicy procesu znaczyłaby dwie różne rzeczy (CLAUDE.md -> „Warstwy kodu").

    Flow:
        1. `get_engine()` (`factory.py`) buduje silnik wskazany przez `ANONYMIZATION_ENGINE`
           i pada przy starcie, gdy konfiguracja jest błędna.
        2. Trasa woła `anonymize()` z tekstem z żądania.
        3. Silnik oddaje tekst ze znacznikami i zapisuje wywołanie przez `_log_call()`.

    Implementacje są async, choć atrapa niczego nie czeka: prawdziwy silnik (wzorce, NER) będzie
    liczył na CPU i trafi do wątku roboczego, a trasa nie ma się wtedy zmieniać.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Description:
        Nazwa silnika, odsyłana w każdej odpowiedzi. Po niej `api` rozpoznaje atrapę i odmawia jej
        wyniku przy prawdziwym modelu.

        Example args:
            (brak)

        Example result:
            "fake"
        """

    @abstractmethod
    async def anonymize(
        self,
        text: str,  # np. "Jan Nowak zgłasza, że przesyłki nie przychodzą."
    ) -> str:
        """
        Description:
        Zamienia dane w tekście na znaczniki swojego rodzaju i oddaje tekst wynikowy.

        Example args:
            text="Jan Nowak zgłasza, że przesyłki nie przychodzą."

        Example result:
            "{IMIĘ} {NAZWISKO} zgłasza, że przesyłki nie przychodzą."

        Raises:
            EngineError: tekstu nie da się zanonimizować
        """

    def _log_call(
        self,
        text:   str,  # np. "Jan Nowak zgłasza…" — tekst wejściowy
        result: str,  # np. "{IMIĘ} {NAZWISKO} zgłasza…" — tekst wynikowy
    ) -> None:
        """
        Description:
        Zapisuje jedno wywołanie, w jednym kształcie dla każdego silnika. Same długości, na
        każdym poziomie logu: wejście to surowe zgłoszenie z danymi osobowymi, a wynik może nieść
        to, czego silnik nie złapał.

        Example args:
            text="Jan Nowak zgłasza…"
            result="{IMIĘ} {NAZWISKO} zgłasza…"

        Example result:
            None — jeden wpis INFO z nazwą silnika i długościami
        """
        logger.info(
            "anonymize engine=%s chars_in=%d chars_out=%d",
            self.name,
            len(text),
            len(result),
        )
