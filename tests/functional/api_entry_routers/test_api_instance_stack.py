import httpx2
import pytest

pytestmark = [pytest.mark.stack, pytest.mark.stack_api]

# Część wdrożeniowa: kształt odpowiedzi i stany sprawdza test w procesie. Tu zostaje to, czego
# bez kontenera nie da się dowieść: że `api` dosięga Qdranta i Postgresa po nazwach usług
# z konfiguracji i czyta katalog paczki kodu. Stanów nie sprawdzamy, bo zależą od tego, co
# deweloper zbudował.

# Pięć indeksów w kolejności, w jakiej podaje je trasa.
INDEXES = [
    ("tickets", "cards"),
    ("tickets", "threads"),
    ("docs",    "sections"),
    ("docs",    "fragments"),
    ("code",    "package"),
]


def test_instance_answers_from_the_running_container(api_client: httpx2.Client) -> None:
    """Sprawdza, czy uruchomiony kontener `api` odpowiada na `GET /instance` statusem 200 z pięcioma
    indeksami w stałej kolejności, każdym w jednym ze stanów `missing`, `empty` albo `built`,
    i z anonimizatorem dostępnym, z nazwą silnika.

    Wyłapuje wdrożenie, w którym kontener nie dosięga Qdranta albo Postgresa (status 503), nie
    ma konfiguracji bazy (500), nie dosięga usługi `anonymizer` albo nie wystawia trasy — test
    w procesie stoi na atrapach klientów i tego nie widzi."""
    response = api_client.get("/instance")

    assert response.status_code == 200

    indexes = response.json()["indexes"]

    assert [(item["material"], item["index"]) for item in indexes] == INDEXES
    assert {item["state"] for item in indexes} <= {"missing", "empty", "built"}
    assert response.json()["anonymization"]["state"] == "available"
    assert response.json()["anonymization"]["engine"]
