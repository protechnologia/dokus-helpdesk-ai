import httpx

from app.db_qdrant.errors import DbQdrantConfigError, DbQdrantError


class QdrantClient:
    """
    Description:
    Połączenie `api` z usługą `qdrant` i nic więcej: żądanie HTTP, tłumaczenie błędów, zamknięcie.
    „Klient" znaczy przekroczenie granicy procesu (CLAUDE.md -> „Warstwy kodu") — każda awaria tej
    rozmowy kończy się tutaj i staje się `DbQdrantError`, a `httpx` jest importowany wyłącznie
    w tym pliku.

    Do czego:
    Warstwa niskopoziomowa pakietu `app/db_qdrant/`. Nie zna żadnej kolekcji — dostaje metodę,
    ścieżkę i treść żądania, a oddaje odpowiedź jako słownik. Żądania składają klasy kolekcji
    z `collection/` i TYLKO one wołają `request()` i `get_or_none()`: kod spoza `app/db_qdrant/`
    buduje klienta, podaje go kolekcji i nigdy nie pyta Qdranta sam. Jeden klient obsługuje
    wszystkie kolekcje.

    Flow:
        1. Budowany raz z `Settings` (adres, timeout) i używany wielokrotnie.
        2. `request()` wykonuje jedno żądanie; `get_or_none()` to odczyt, przy którym „nie ma"
           jest odpowiedzią, a nie błędem.
        3. `aclose()` zamyka połączenia.

    Piszemy wprost na REST Qdranta, bez `qdrant-client`: użytych końcówek jest kilka, `httpx`
    i tak jest zależnością, a warstwa pośrednia ukryłaby to, co tu kontrolujemy ręcznie — nazwane
    wektory i metrykę (CLAUDE.md -> „Świadomie pominięte").
    """

    def __init__(
        self,
        base_url: str,           # np. "http://qdrant:6333"
        timeout:  float = 30.0,  # sekundy
    ):
        """
        Description:
        Buduje klienta jednej instancji Qdranta. Odmawia pustego adresu: to on powstaje, gdy
        zmienna nie dotrze do kontenera, a klient zbudowany na nim pada dopiero przy pierwszym
        żądaniu, nieczytelnym błędem względnego adresu.

        Example args:
            base_url="http://qdrant:6333"
            timeout=30.0

        Example result:
            QdrantClient dla http://qdrant:6333

        Raises:
            DbQdrantConfigError: pusty `QDRANT_URL`
        """
        if not base_url.strip():
            raise DbQdrantConfigError("QDRANT_URL nie może być puste")

        self._client = httpx.AsyncClient(
            base_url = base_url.rstrip("/"),  # ukośnik na końcu zdublowałby się ze ścieżkami
            timeout  = timeout,
        )

    async def request(
        self,
        method: str,                 # np. "PUT"
        path:   str,                 # np. "/collections/tickets"
        params: dict | None = None,  # np. {"wait": "true"}
        json:   dict | None = None,  # np. {"vectors": {"problem": {"size": 768, …}}}
    ) -> dict:
        """
        Description:
        Wykonuje jedno żądanie i oddaje odpowiedź jako słownik. Każdy status poza 2xx to błąd.

        Example args:
            method="PUT"
            path="/collections/tickets"
            json={"vectors": {"problem": {"size": 768, "distance": "Cosine"}}}

        Example result:
            {"result": True, "status": "ok"}

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, odpowiedział błędem albo treścią, która nie
                jest obiektem JSON
        """
        response = await self._send(method, path, params=params, json=json)

        self._require_success(response, method, path)

        return self._decode(response)

    async def get_or_none(
        self,
        path: str,  # np. "/collections/tickets"
    ) -> dict | None:
        """
        Description:
        Odczyt, przy którym brak jest odpowiedzią: 404 wraca jako `None`. Tak pyta się
        o kolekcję — jej nieistnienie to zwykły stan początkowy, a nie awaria.

        Example args:
            path="/collections/tickets"

        Example result:
            {"result": {"config": {"params": {"vectors": {"problem": {"size": 768}, …}}}}}

        Raises:
            DbQdrantError: Qdrant nie odpowiedział albo odpowiedział statusem innym niż 2xx i 404
        """
        response = await self._send("GET", path)

        # Jedyny status, który jest odpowiedzią, a nie porażką: nie ma takiego zasobu.
        if response.status_code == 404:
            return None

        self._require_success(response, "GET", path)

        return self._decode(response)

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia. Otwarta pula trzyma gniazda, a testy ostrzegają o niezamkniętych
        transportach. Powtórne wywołanie nic nie robi.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._client.aclose()

    async def _send(
        self,
        method: str,                 # np. "POST"
        path:   str,                 # np. "/collections/tickets/points/query"
        params: dict | None = None,  # np. {"wait": "true"}
        json:   dict | None = None,  # np. {"query": [0.0123, -0.0456], "limit": 5}
    ) -> httpx.Response:
        """
        Description:
        Wysyła żądanie i oddaje odpowiedź, jakakolwiek by była. Jedyne miejsce, w którym awarie
        transportu stają się `DbQdrantError`, więc żaden wołający nie widzi typów `httpx`.

        Example args:
            method="POST"
            path="/collections/tickets/points/count"
            json={"exact": True}

        Example result:
            <Response [200 OK]>

        Raises:
            DbQdrantError: Qdrant nie odpowiedział w czasie albo nie da się z nim połączyć
        """
        try:
            response = await self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:  # nie odpowiedział w czasie
            raise DbQdrantError(f"Qdrant nie odpowiedział w czasie: {method} {path}") from exc
        except httpx.HTTPError as exc:         # odmowa połączenia, DNS, zerwany transport
            raise DbQdrantError(f"nie da się połączyć z Qdrantem: {exc}") from exc

        return response

    def _require_success(
        self,
        response: httpx.Response,  # np. 400 z treścią „Wrong input: Vector dimension error"
        method:   str,             # np. "PUT"
        path:     str,             # np. "/collections/tickets/points"
    ) -> None:
        """
        Description:
        Zamienia odpowiedź o statusie innym niż 2xx na `DbQdrantError`.

        Example args:
            response=<Response [400 Bad Request]>
            method="PUT"
            path="/collections/tickets/points"

        Example result:
            None — status 2xx

        Raises:
            DbQdrantError: status inny niż 2xx
        """
        if response.is_success:
            return None

        # Qdrant tłumaczy odmowę w treści odpowiedzi (zły wymiar wektora, nieznana nazwa wektora).
        # To tekst usługi, nie klienta, i jedyne miejsce, które mówi DLACZEGO.
        raise DbQdrantError(
            f"Qdrant odpowiedział HTTP {response.status_code} na {method} {path}: "
            f"{response.text[:200]}"
        )

    def _decode(
        self,
        response: httpx.Response,  # np. 200 z {"result": {…}, "status": "ok"}
    ) -> dict:
        """
        Description:
        Zamienia udaną odpowiedź na słownik. Osobno od żądania, żeby „treść nie jest tym, czego
        oczekujemy" było jedną porażką z jednym komunikatem.

        Example args:
            response=<Response [200 OK]>

        Example result:
            {"result": {"status": "green"}, "status": "ok"}

        Raises:
            DbQdrantError: treść nie jest JSON-em albo nie jest obiektem
        """
        try:
            body = response.json()
        except ValueError as exc:  # 200 z treścią spoza JSON-a — zwykle strona błędu proxy
            raise DbQdrantError("Qdrant odpowiedział treścią, która nie jest JSON-em") from exc

        if not isinstance(body, dict):
            raise DbQdrantError(
                f"Qdrant odpowiedział typem {type(body).__name__}, a nie obiektem JSON"
            )

        return body
