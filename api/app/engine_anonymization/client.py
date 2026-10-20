import logging

import httpx

from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.errors import AnonymizationConfigError, AnonymizationError
from app.engine_anonymization.models import AnonymizedText, AnonymizerInfo

logger = logging.getLogger(__name__)

# Ścieżka anonimizacji w usłudze `anonymizer`. Stała, a nie ustawienie: to część kontraktu między
# dwiema usługami, które wdrażamy razem; gdzie usługa stoi, mówi już `ANONYMIZATION_BASE_URL`.
ANONYMIZE_PATH = "/anonymize"

# Ścieżka opisu usługi: silnik i model, bez adresu serwera modelu i bez klucza.
INFO_PATH = "/info"

# Opis usługi, która nie odpowiedziała albo odpowiedziała spoza kontraktu.
UNAVAILABLE = AnonymizerInfo(available=False, engine=None, model=None)

# Nazwa atrapy silnika w odpowiedzi usługi — ta sama, którą usługa zapisuje w `FAKE_ENGINE_NAME`.
# Atrapa oddaje tekst bez zmian, więc jej wynik ten klient oddaje tylko wtedy, gdy mu na to
# pozwolono (`fake_engine_allowed`).
FAKE_ENGINE = "fake"


class AnonymizerClient(Anonymizer):
    """
    Description:
    Jedyny anonimizator, którego `api` używa w czasie działania: klient HTTP usługi `anonymizer`.
    „Klient", bo przekracza granicę procesu (CLAUDE.md -> „Warstwy kodu"); to, co po drugiej
    stronie zamienia dane na znaczniki, nazywa się silnikiem. Czy silnik jest atrapą, decyduje
    konfiguracja usługi, a nie `api`.

    Flow:
        1. Budowany raz na proces z `Settings` (adres, limit czasu, zgoda na atrapę silnika)
           i używany wielokrotnie.
        2. `anonymize()` wysyła tekst do `/anonymize` i czyta odpowiedź: tekst i nazwę silnika.
        3. Wynik atrapy silnika bez zgody to `AnonymizationConfigError`, nie tekst: atrapa oddaje
           tekst bez zmian, a ten nie może trafić do modelu zewnętrznego. Każda inna porażka to
           `AnonymizationError` (fail-closed: graf staje).
        4. `describe()` pyta `/info`, którym silnikiem i z jakim modelem usługa działa; usługa,
           która nie odpowiada, jest opisana jako niedostępna, bez błędu.
        5. `aclose()` zamyka połączenia przy wyłączaniu aplikacji.

    Odmowa atrapy stoi tutaj, a nie w fabryce, bo fabryka z niczym się nie łączy, a który silnik
    działa, wie dopiero usługa. Zabezpieczenie jest więc przy pierwszym wywołaniu, a nie przy
    budowie — ale przed modelem, więc surowy tekst nadal z procesu nie wychodzi.
    """

    def __init__(
        self,
        base_url:            str,           # np. "http://anonymizer:8000"
        fake_engine_allowed: bool,          # np. True — przy atrapie modelu generującego
        timeout:             float = 30.0,  # sekundy
    ):
        """
        Description:
        Buduje klienta jednej instancji usługi. Odmawia pustego adresu: `httpx` by go przyjął
        i padł dopiero przy żądaniu, niezrozumiałym błędem względnego adresu.

        Zgoda na atrapę silnika nie ma wartości domyślnej: od niej zależy, czy surowy tekst może
        pójść dalej, więc wołający podaje ją zawsze wprost.

        Example args:
            base_url="http://anonymizer:8000"
            fake_engine_allowed=False
            timeout=30.0

        Example result:
            AnonymizerClient wysyłający do http://anonymizer:8000/anonymize i odmawiający
            wyniku atrapy silnika

        Raises:
            AnonymizationConfigError: `ANONYMIZATION_BASE_URL` jest puste
        """
        # Compose wstawia pusty napis za niezdefiniowane `${VAR:-}`.
        if not base_url.strip():
            raise AnonymizationConfigError("ANONYMIZATION_BASE_URL nie może być puste")

        self._fake_engine_allowed = fake_engine_allowed
        self._client              = httpx.AsyncClient(
            base_url = base_url.rstrip("/"),  # ukośnik na końcu zdublowałby się ze ścieżką
            timeout  = timeout,
        )

    async def anonymize(
        self,
        text: str,  # np. "Jan Nowak zgłasza, że przesyłki nie przychodzą."
    ) -> AnonymizedText:
        """
        Description:
        Wysyła tekst do usługi i oddaje go po anonimizacji. Jedyne miejsce, w którym awarie
        transportu stają się `AnonymizationError`, więc nikt wyżej nie widzi typów `httpx`.

        Example args:
            text="Jan Nowak zgłasza, że przesyłki nie przychodzą."

        Example result:
            AnonymizedText(text="{IMIĘ} {NAZWISKO} zgłasza, że przesyłki nie przychodzą.")

        Raises:
            AnonymizationConfigError: usługa działa na atrapie silnika, a klient nie ma na nią
                zgody
            AnonymizationError: usługa nie odpowiedziała, odpowiedziała błędem albo treścią,
                która nie jest kontraktem
        """
        # --- wywołanie ---
        try:
            response = await self._client.post(ANONYMIZE_PATH, json={"text": text})
            response.raise_for_status()
        except httpx.TimeoutException as exc:  # usługa nie odpowiedziała w czasie
            raise AnonymizationError("anonimizator nie odpowiedział w czasie") from exc
        except httpx.HTTPStatusError as exc:   # odpowiedziała, ale statusem spoza 2xx
            raise AnonymizationError(
                f"anonimizator odpowiedział HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:         # odmowa połączenia, DNS, zerwany transport
            raise AnonymizationError(f"nie da się połączyć z anonimizatorem: {exc}") from exc

        anonymized, engine = self._read_response(response)

        # Same długości i nazwa silnika: wejście to surowe zgłoszenie (CLAUDE.md -> „Logi").
        logger.info(
            "anonymize engine=%s chars_in=%d chars_out=%d",
            engine,
            len(text),
            len(anonymized.text),
        )

        return anonymized

    async def describe(self) -> AnonymizerInfo:
        """
        Description:
        Pyta usługę, którym silnikiem i z jakim modelem anonimizuje. Usługa nie łączy się przy
        tym z modelem, więc odpowiada także przy wyłączonym serwerze modelu. Brak odpowiedzi,
        status spoza 2xx i treść spoza kontraktu dają opis „niedostępna", a nie błąd: czyta to
        opis instancji, który ma pokazać brak anonimizatora, zamiast samemu zawieść.

        Example args:
            (brak)

        Example result:
            AnonymizerInfo(available=True, engine="agent",
                           model="speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic")
        """
        # --- wywołanie ---
        try:
            response = await self._client.get(INFO_PATH)
            response.raise_for_status()
            payload = response.json()
        except (
            httpx.HTTPError,  # brak połączenia, przekroczony czas albo status spoza 2xx
            ValueError,       # treść spoza JSON-a, zwykle strona błędu pośrednika
        ) as exc:
            logger.warning("anonymizer info unavailable error=%s", type(exc).__name__)

            return UNAVAILABLE

        # --- kontrakt: nazwa silnika jest zawsze, model bywa `null` ---
        engine = payload.get("engine") if isinstance(payload, dict) else None
        model  = payload.get("model") if isinstance(payload, dict) else None

        if not isinstance(engine, str) or not engine or not isinstance(model, str | None):
            logger.warning("anonymizer info unavailable error=contract")

            return UNAVAILABLE

        info = AnonymizerInfo(available=True, engine=engine, model=model)

        return info

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia. Woła to aplikacja przy wyłączaniu; powtórne wywołanie nic nie robi.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._client.aclose()

    def _read_response(
        self,
        response: httpx.Response,  # np. 200 z {"text": "{IMIĘ} …", "engine": "agent"}
    ) -> tuple[AnonymizedText, str]:
        """
        Description:
        Czyta tekst i nazwę silnika z udanej odpowiedzi i odmawia wyniku atrapy, gdy klient nie
        ma na nią zgody. Osobno od wywołania, żeby reguły kontraktu dało się sprawdzić bez
        transportu. Komunikaty nie cytują treści: odpowiedź może nieść to, czego silnik nie
        złapał.

        Example args:
            response=<Response [200 OK]>

        Example result:
            (AnonymizedText(text="{IMIĘ} {NAZWISKO} zgłasza…"), "agent")

        Raises:
            AnonymizationConfigError: odpowiedź pochodzi od atrapy silnika, a klient nie ma na
                nią zgody
            AnonymizationError: treść nie jest JSON-em albo nie ma tekstu lub nazwy silnika
        """
        # --- treść ---
        try:
            payload = response.json()
        except ValueError as exc:  # 200 z treścią spoza JSON-a — zwykle strona błędu pośrednika
            raise AnonymizationError("anonimizator odpowiedział treścią spoza JSON-a") from exc

        if not isinstance(payload, dict):
            raise AnonymizationError("anonimizator odpowiedział czymś innym niż obiekt JSON")

        engine = payload.get("engine")
        text   = payload.get("text")

        # --- silnik: najpierw, bo od niego zależy, czy tekst w ogóle wolno oddać ---
        if not isinstance(engine, str) or not engine:
            raise AnonymizationError("odpowiedź anonimizatora nie ma nazwy silnika")

        # Zgodę daje fabryka przy atrapie modelu: tekst nie trafia wtedy do żadnego modelu.
        if engine == FAKE_ENGINE and not self._fake_engine_allowed:
            raise AnonymizationConfigError(
                "usługa anonymizer działa na atrapie silnika (ANONYMIZATION_ENGINE=fake), która "
                "oddaje tekst bez zmian — przy prawdziwym modelu generującym jej wyniku nie wolno "
                "użyć"
            )

        # --- tekst ---
        if not isinstance(text, str) or not text:
            raise AnonymizationError("odpowiedź anonimizatora nie ma tekstu")

        result = (AnonymizedText(text=text), engine)

        return result
