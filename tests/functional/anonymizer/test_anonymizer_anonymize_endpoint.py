import logging

import pytest
from fastapi.testclient import TestClient

from anonymizer_app.main import create_app
from tests._helpers.anonymization import FAKE_ENGINE, RAW_TEXT, SENSITIVE


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
