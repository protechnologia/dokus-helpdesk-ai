import logging

import httpx

from app.engine_embedding.errors import EmbeddingConfigError, EmbeddingError
from app.engine_embedding.models import Embeddings

logger = logging.getLogger(__name__)

# Ścieżka embeddingu w usłudze `embedder`. Stała, a nie ustawienie: to część kontraktu między
# dwiema usługami, które wdrażamy razem; gdzie usługa stoi, mówi już `EMBEDDING_BASE_URL`.
EMBED_PATH = "/embed"


class EmbeddingClient:
    """
    Description:
    Droga `api` od tekstu do wektorów: klient HTTP usługi `embedder`. „Klient", bo przekracza
    granicę procesu (CLAUDE.md -> „Warstwy kodu"); to, co po drugiej stronie liczy wektory,
    nazywa się `Encoder`, nigdy klientem.

    Flow:
        1. Budowany raz z `Settings` (adres, limit czasu) i używany wielokrotnie; `httpx`
           trzyma połączenia między wywołaniami.
        2. Kod domeny woła `embed_query()`, `embed_passage()` albo `embed_sts()` — nigdy
           ogólnego `embed(mode=…)`.
        3. Każda z nich wysyła partię do `/embed` ze swoim trybem i oddaje `Embeddings`: wektor
           na tekst, w kolejności tekstów, i nazwę modelu, który je policzył.

    Dlaczego trzy metody, a nie jedna z argumentem `mode`: tryb decyduje, do której przestrzeni
    wektorowej należy wynik, a pomieszanie przestrzeni psuje wyszukiwanie po cichu (CLAUDE.md ->
    „Embeddingi"). Argument da się przekazać ze zmiennej trzy wywołania dalej i nikt nie zauważy,
    który tryb leci; trzy nazwane metody wymuszają wybór w miejscu wywołania. Same prefiksy żyją
    w usłudze `embedder`, bo to, co tryb ZNACZY, jest cechą modelu, nie tego kontraktu.

    Atrapy embeddera ten klient nie odrzuca: o atrapie decyduje konfiguracja usługi
    (`EMBEDDING_BACKEND`), a szkodzi ona dopiero przy mieszaniu modeli w jednej kolekcji — tego
    pilnuje Qdrant po nazwie modelu z wyniku.
    """

    def __init__(
        self,
        base_url: str,          # np. "http://embedder:8000"
        timeout:  float = 30.0, # sekundy
    ):
        """
        Description:
        Buduje klienta jednej instancji usługi `embedder`. Odmawia pustego adresu: `httpx` by go
        przyjął i padł dopiero przy żądaniu, niezrozumiałym błędem względnego adresu, daleko od
        przyczyny.

        Example args:
            base_url="http://embedder:8000"
            timeout=30.0

        Example result:
            EmbeddingClient wysyłający do http://embedder:8000/embed

        Raises:
            EmbeddingConfigError: `EMBEDDING_BASE_URL` jest puste
        """
        # Strażnik, nie uprzejmość: compose wstawia PUSTY NAPIS za niezdefiniowane `${VAR:-}`,
        # a klient zbudowany na "" pada przy żądaniu nieczytelnym komunikatem.
        if not base_url.strip():
            raise EmbeddingConfigError("EMBEDDING_BASE_URL nie może być puste")

        self._client = httpx.AsyncClient(
            base_url = base_url.rstrip("/"),  # ukośnik na końcu zdublowałby się z EMBED_PATH
            timeout  = timeout,
        )

    async def embed_query(
        self,
        texts: list[str],  # np. ["Nie działa wysyłka do ePUAP"]
    ) -> Embeddings:
        """
        Description:
        Liczy wektory NOWYCH zgłoszeń zadanych jako pytanie do indeksu — strona wyszukiwania
        w czasie działania. Wynik wolno porównywać wyłącznie z wektorami `passage`, nigdy `sts`.

        Example args:
            texts=["Nie działa wysyłka do ePUAP"]

        Example result:
            Embeddings(model="OPI-PIB/PolDense-150M", vectors=[[0.0123, -0.0456, …]])

        Raises:
            EmbeddingError: embedder jest nieosiągalny, nie odpowiedział w czasie albo
                odpowiedział błędem
        """
        return await self._embed(texts, "query")

    async def embed_passage(
        self,
        texts: list[str],  # np. ["Brak tonera w drukarce sieciowej"]
    ) -> Embeddings:
        """
        Description:
        Liczy wektory historycznych zgłoszeń i fragmentów dokumentacji przy INDEKSACJI — tego,
        z czym porównuje się zapytanie.

        Example args:
            texts=["Brak tonera w drukarce sieciowej"]

        Example result:
            Embeddings(model="OPI-PIB/PolDense-150M", vectors=[[0.0123, -0.0456, …]])

        Raises:
            EmbeddingError: embedder jest nieosiągalny, nie odpowiedział w czasie albo
                odpowiedział błędem
        """
        return await self._embed(texts, "passage")

    async def embed_sts(
        self,
        texts: list[str],  # np. ["Brak tonera w drukarce sieciowej"]
    ) -> Embeddings:
        """
        Description:
        Liczy wektory do porównania SYMETRYCZNEGO, zgłoszenie ze zgłoszeniem. Obie strony
        takiego porównania liczy się w tym trybie — model uczono z prefiksem po obu stronach,
        nie po jednej.

        Example args:
            texts=["Brak tonera w drukarce sieciowej"]

        Example result:
            Embeddings(model="OPI-PIB/PolDense-150M", vectors=[[0.0123, -0.0456, …]])

        Raises:
            EmbeddingError: embedder jest nieosiągalny, nie odpowiedział w czasie albo
                odpowiedział błędem
        """
        return await self._embed(texts, "sts")

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia. Woła to aplikacja przy wyłączaniu — otwarta pula trzyma gniazda,
        a testy ostrzegają o niezamkniętym transporcie.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._client.aclose()

    async def _embed(
        self,
        texts: list[str],  # np. ["Brak tonera"]
        mode:  str,        # np. "passage" — jeden z query/passage/sts
    ) -> Embeddings:
        """
        Description:
        Wysyła jedną partię w jednym trybie i czyta odpowiedź. Jedyne miejsce, w którym awarie
        transportu stają się `EmbeddingError`, więc nikt wyżej nie widzi typów `httpx`.

        Example args:
            texts=["Brak tonera"]
            mode="passage"

        Example result:
            Embeddings(model="OPI-PIB/PolDense-150M", vectors=[[0.0123, -0.0456, …]])

        Raises:
            EmbeddingError: transport zawiódł, usługa odpowiedziała statusem spoza 2xx albo
                treścią, która nie jest kontraktem
        """
        # Liczby i tryb — teksty to treść zgłoszeń, czyli dane klienta, najwyżej na DEBUG
        # (CLAUDE.md -> „Logi i obserwowalność").
        logger.info("embed mode=%s batch_size=%d", mode, len(texts))

        # --- wywołanie ---
        try:
            response = await self._client.post(EMBED_PATH, json={"texts": texts, "mode": mode})
            response.raise_for_status()
        except httpx.TimeoutException as exc:  # embedder nie odpowiedział w czasie
            raise EmbeddingError(f"Embedder timed out after {len(texts)} text(s)") from exc
        except httpx.HTTPStatusError as exc:   # odpowiedział, ale statusem spoza 2xx
            raise EmbeddingError(
                f"Embedder returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:         # odmowa połączenia, DNS, zerwany transport
            raise EmbeddingError(f"Could not reach the embedder: {exc}") from exc

        return self._read_response(response, expected=len(texts))

    def _read_response(
        self,
        response: httpx.Response,  # np. 200 z {"vectors": [[…]], "model": "…", "dimension": 768}
        expected: int,             # np. 1 — ile tekstów wysłano
    ) -> Embeddings:
        """
        Description:
        Czyta wektory i nazwę modelu z udanej odpowiedzi i sprawdza liczbę wektorów. Osobno od
        wywołania, żeby reguły kontraktu dało się sprawdzić bez transportu, a `_embed` czytało
        się jak „wywołaj, potem odczytaj".

        Example args:
            response=<Response [200 OK]>
            expected=1

        Example result:
            Embeddings(model="OPI-PIB/PolDense-150M", vectors=[[0.0123, -0.0456, …]])

        Raises:
            EmbeddingError: treść nie jest JSON-em, nie ma `vectors` albo `model`, albo niesie
                inną liczbę wektorów niż tekstów
        """
        # --- treść ---
        try:
            payload = response.json()
        except ValueError as exc:  # 200 z treścią spoza JSON-a — zwykle strona błędu pośrednika
            raise EmbeddingError("Embedder returned a non-JSON body") from exc

        vectors = payload.get("vectors")
        model   = payload.get("model")

        if vectors is None:
            raise EmbeddingError("Embedder response has no 'vectors' field")

        # Bez nazwy modelu nie da się sprawdzić, czy wektor pasuje do kolekcji, z którą go
        # porównamy — a wektory dwóch modeli o tym samym wymiarze wyglądają tak samo.
        if not isinstance(model, str) or not model:
            raise EmbeddingError("Embedder response has no 'model' field")

        # --- liczba ---
        # Wektor na tekst, w kolejności — na tym stoi cały kontrakt: wołający zipują wektory
        # z powrotem na zgłoszenia, z których powstały. Rozjazd przypisałby wektor nie temu
        # zgłoszeniu — złe odpowiedzi zamiast błędu, więc łapiemy go tutaj.
        if len(vectors) != expected:
            raise EmbeddingError(
                f"Embedder returned {len(vectors)} vector(s) for {expected} text(s)"
            )

        embeddings = Embeddings(model=model, vectors=vectors)

        return embeddings
