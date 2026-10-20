import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests._helpers.instance import (
    app_with_inspector,
    counting_postgres,
    failing_qdrant,
    inspector_on,
    scripted_inspector,
)
from tests._helpers.synthetic_code import synthetic_code_description


def test_instance_reports_the_model_and_the_state_of_every_index() -> None:
    """Sprawdza, czy `GET /instance` odpowiada statusem 200 z atrapą modelu bez nazwy, z pięcioma
    indeksami w stałej kolejności, każdym ze stanem i liczbą z serwisu (karty zbudowane, wątki
    puste, dokumentacji nie ma, kod zbudowany), i z gałęzią oraz dniem budowy paczki syntetycznej.

    Wyłapuje trasę, która nie jest podpięta, gubi pole odpowiedzi albo wystawia stan inaczej niż
    jako `missing`, `empty` i `built` — z tej odpowiedzi belka frontu rysuje, na czym stoi
    pokaz."""
    package = synthetic_code_description().read_package_info()
    client  = TestClient(app_with_inspector(scripted_inspector(cards=171, threads=0)))

    response = client.get("/instance")

    assert response.status_code == 200
    assert response.json() == {
        "model":        {"provider": "fake", "name": None},
        "indexes":      [
            {"material": "tickets", "index": "cards",     "state": "built",   "count": 171},
            {"material": "tickets", "index": "threads",   "state": "empty",   "count": 0},
            {"material": "docs",    "index": "sections",  "state": "missing", "count": None},
            {"material": "docs",    "index": "fragments", "state": "missing", "count": None},
            {"material": "code",    "index": "package",   "state": "built",   "count": 30},
        ],
        "code_package": {"branch": package.branch, "built_on": package.built_on.isoformat()},
    }


def test_instance_reads_the_generation_model_on_every_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy po zmianie dostawcy i modelu generującego w zmiennych środowiskowych ta sama
    aplikacja podaje w `GET /instance` nowego dostawcę i nazwę modelu.

    Wyłapuje trasę, która zapamiętuje konfigurację przy starcie aplikacji: belka pokazywałaby
    model, na którym aplikacja już nie chodzi, tak jak fabryka grafów czyta konfigurację przy
    każdym żądaniu."""
    client = TestClient(app_with_inspector(scripted_inspector()))

    before = client.get("/instance").json()["model"]

    monkeypatch.setenv("LLM_GENERATION_PROVIDER", "openai")
    monkeypatch.setenv("LLM_GENERATION_MODEL", "gpt-6.1-sol")

    after = client.get("/instance").json()["model"]

    assert before == {"provider": "fake", "name": None}
    assert after  == {"provider": "openai", "name": "gpt-6.1-sol"}


def test_a_qdrant_failure_is_a_503_with_the_shared_error_shape() -> None:
    """Sprawdza, czy Qdrant odpowiadający błędem 500 kończy `GET /instance` statusem 503
    w kształcie wspólnym dla błędów (`detail` i `request_id`), a nie odpowiedzią z indeksami
    w stanie `missing`.

    Wyłapuje awarię bazy pokazaną jako niezbudowany indeks albo jako surowy błąd 500: wołający
    nie odróżniłby „spróbuj za chwilę" od „indeksu nie ma"."""
    inspector = inspector_on(
        qdrant   = failing_qdrant(),
        threads  = counting_postgres(0),
        sections = counting_postgres(0),
        code     = synthetic_code_description(),
    )
    client = TestClient(app_with_inspector(inspector), raise_server_exceptions=False)

    response = client.get("/instance")

    assert response.status_code     == 503
    assert set(response.json())     == {"detail", "request_id"}
    assert response.json()["detail"]


def test_openapi_describes_the_instance_response() -> None:
    """Sprawdza, czy schemat OpenAPI aplikacji `api` ma trasę `GET /instance` z odpowiedzią 200
    opisaną modelem `InstanceResponse`.

    Wyłapuje trasę bez opisanego kształtu odpowiedzi: front i helpdesk generują klienta ze
    schematu, więc nie wiedzieliby, jakie pola przyjdą."""
    schema = TestClient(create_app()).get("/openapi.json").json()

    answer = schema["paths"]["/instance"]["get"]["responses"]["200"]["content"]["application/json"]

    assert answer["schema"] == {"$ref": "#/components/schemas/InstanceResponse"}
