import logging

import pytest
from fastapi.testclient import TestClient

from anonymizer_app.core_engine import AgentEngine, get_engine
from anonymizer_app.engine_llm import LLMClient
from anonymizer_app.main import create_app
from tests._helpers.anonymization import ANONYMIZED_TEXT, FAKE_ENGINE, RAW_TEXT, SENSITIVE
from tests._helpers.anonymizer_llm import model_client_on, scripted_llm
from tests._helpers.transport import always


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Prawdziwa usługa `anonymizer` w procesie, na domyślnym silniku. Kontrakt — statusy,
    walidacja, kształt odpowiedzi — to fakty o naszym kodzie, więc sprawdza się je tutaj, a nie
    na kontenerze.

    Example args:
        (brak)

    Example result:
        TestClient nad usługą z GET /health i POST /anonymize
    """
    return TestClient(create_app())


def test_the_text_comes_back_with_the_engine_name(client: TestClient) -> None:
    """Sprawdza, czy `POST /anonymize` odpowiada statusem 200, tekstem i nazwą silnika, który go
    wytworzył — na domyślnej atrapie tekst bez zmian i silnik „fake".

    Wyłapuje odpowiedź bez nazwy silnika albo z inną treścią niż kontrakt: klient w `api`
    rozpoznaje atrapę wyłącznie po tej nazwie, więc bez niej przepuściłby tekst bez
    anonimizacji."""
    response = client.post("/anonymize", json={"text": RAW_TEXT})

    assert response.status_code == 200
    assert response.json()      == {"text": RAW_TEXT, "engine": FAKE_ENGINE}


@pytest.mark.parametrize(
    "body",
    [{"text": ""}, {}, {"txt": RAW_TEXT}],
    ids=["pusty", "brak", "literówka"],
)
def test_a_request_without_text_is_rejected(client: TestClient, body: dict) -> None:
    """Sprawdza, czy żądanie z pustym tekstem, bez tekstu albo z literówką w nazwie pola dostaje
    status 422 we wspólnym kształcie błędu.

    Wyłapuje usługę, która przyjmuje pusty tekst i oddaje pusty wynik: w `api` wyglądałoby to
    jak zgłoszenie bez treści, a nie jak błąd wołającego."""
    response = client.post("/anonymize", json=body)

    assert response.status_code     == 422
    assert response.json()["detail"] == "Request validation failed"


def test_a_rejected_request_echoes_no_text(client: TestClient) -> None:
    """Sprawdza, czy odpowiedź 422 na żądanie z błędnym typem pola (lista z tekstem zgłoszenia
    zamiast tekstu) nie powtarza żadnego fragmentu danych osobowych.

    Wyłapuje odpowiedź błędu, która cytuje przysłaną wartość: to surowe zgłoszenie, a odpowiedź
    błędu trafia do logów wołającego."""
    response = client.post("/anonymize", json={"text": [RAW_TEXT]})

    assert response.status_code == 422
    assert not [fragment for fragment in SENSITIVE if fragment in response.text]


@pytest.mark.parametrize("body", [{"text": RAW_TEXT}, {"text": [RAW_TEXT]}], ids=["udane", "422"])
def test_no_request_logs_the_text(
    client: TestClient,
    body:   dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sprawdza, czy ani udana anonimizacja, ani żądanie odrzucone walidacją nie zapisują w logu
    usługi, na żadnym poziomie, także DEBUG, fragmentu danych osobowych ze zgłoszenia.

    Wyłapuje wpis w logu z treścią żądania, także w obsłudze błędu walidacji, której lista błędów
    cytuje przysłane wartości: ta usługa widzi surowe zgłoszenia."""
    with caplog.at_level(logging.DEBUG):
        client.post("/anonymize", json=body)

    assert not [fragment for fragment in SENSITIVE if fragment in caplog.text]


def agent_client(
    llm: LLMClient,  # np. scripted_llm(persons=[{"tekst": "Nowak", "rodzaj": "NAZWISKO"}])
) -> TestClient:
    """
    Description:
    Usługa w procesie z silnikiem `agent` na podanym kliencie modelu, podstawionym trasie przez
    `dependency_overrides` — bez serwera modelu i bez zmiany konfiguracji.

    Example args:
        llm=scripted_llm(persons=[{"tekst": "Nowak", "rodzaj": "NAZWISKO"}])

    Example result:
        TestClient, którego `POST /anonymize` idzie przez graf anonimizacji
    """
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: AgentEngine(llm)

    return TestClient(app)


def test_the_agent_engine_answers_with_markers_and_its_name() -> None:
    """Sprawdza, czy `POST /anonymize` na silniku `agent` odpowiada statusem 200, tekstem ze
    znacznikami (telefon od wzorców, imię i nazwisko od modelu) i nazwą silnika „agent”.

    Wyłapuje trasę, która nie przenosi wyniku grafu albo nazwy silnika: klient w `api` przyjmuje
    wynik tylko po nazwie innej niż „fake”."""
    persons = [{"tekst": "Jan", "rodzaj": "IMIĘ"}, {"tekst": "Nowak", "rodzaj": "NAZWISKO"}]
    client  = agent_client(scripted_llm(persons=persons))

    response = client.post("/anonymize", json={"text": RAW_TEXT})

    assert response.status_code == 200
    assert response.json()      == {"text": ANONYMIZED_TEXT, "engine": "agent"}


def test_a_model_failure_is_503_without_text() -> None:
    """Sprawdza, czy awaria serwera modelu kończy żądanie statusem 503, a odpowiedź nie niesie
    żadnego fragmentu zgłoszenia.

    Wyłapuje odpowiedź 200 z tekstem po samych wzorcach (osoby poszłyby do modelu zewnętrznego)
    i odpowiedź błędu, która cytuje zgłoszenie."""
    llm = model_client_on(always({"error": "pod down"}, status=502))

    response = agent_client(llm).post("/anonymize", json={"text": RAW_TEXT})

    assert response.status_code == 503
    for fragment in SENSITIVE:
        assert fragment not in response.text
