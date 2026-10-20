import httpx2
import pytest

pytestmark = [pytest.mark.stack, pytest.mark.stack_frontend]

# Część wdrożeniowa frontu: logikę bez przeglądarki sprawdza Vitest (`tests/unit/frontend/`).
# Tu zostaje to, czego bez kontenera nie da się dowieść: że obraz się zbudował, port jest
# wystawiony, strona przychodzi, a `/api/…` trafia do usługi `api` bez przedrostka. Test idzie
# na tej warstwie compose, która stoi: w dev odpowiada serwer Vite, na prod nginx.


def test_the_page_comes_from_the_published_port(frontend_client: httpx2.Client) -> None:
    """Sprawdza, czy uruchomiony kontener `frontend` odpowiada pod portem wystawionym na hosta
    stroną HTML z elementem `#root`, w którym montuje się aplikacja.

    Wyłapuje usterkę wdrożenia, której testy bez kontenera nie widzą: obraz się nie zbudował,
    port nie jest wystawiony albo serwer podaje coś innego niż stronę frontu."""
    response = frontend_client.get("/")

    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_an_unknown_path_gets_the_page(frontend_client: httpx2.Client) -> None:
    """Sprawdza, czy ścieżka, której nie ma wśród plików, dostaje tę samą stronę zamiast 404.

    Wyłapuje serwer, który przy odświeżeniu strony pod inną ścieżką (zakładka zapamiętana
    w przeglądarce) oddaje błąd zamiast aplikacji."""
    response = frontend_client.get("/nie-ma-takiej-strony", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_api_paths_reach_the_api_without_the_prefix(frontend_client: httpx2.Client) -> None:
    """Sprawdza, czy `/api/health` i `/api/instance` wywołane przez front odpowiadają tym, co
    odpowiada usługa `api` pod `/health` i `/instance`: statusem 200, `{"status": "ok"}`
    i pięcioma indeksami.

    Wyłapuje przekazywanie, które nie zdejmuje przedrostka `/api` (trasa nie istnieje w `api`),
    wskazuje zły adres usługi albo nie przekazuje wcale — strona wstaje, a każdy guzik kończy się
    błędem."""
    health   = frontend_client.get("/api/health")
    instance = frontend_client.get("/api/instance")

    assert (health.status_code, health.json()) == (200, {"status": "ok"})
    assert instance.status_code == 200
    assert len(instance.json()["indexes"]) == 5
