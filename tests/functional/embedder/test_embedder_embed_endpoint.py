import math

import pytest
from fastapi.testclient import TestClient

from embedder_app.main import create_app

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Builds the real embedder application in-process. This is the CONTRACT half of the split from
    CLAUDE.md -> "Testy": status codes, request validation and payload shape are facts about our
    own code, so they are proven here rather than against a running container.

    Example args:
        (injected by pytest)

    Example result:
        TestClient over the app serving GET /health and POST /embed
    """
    return TestClient(create_app())


def _embed(
    client: TestClient,     # e.g. TestClient(create_app())
    texts:  list[str],      # e.g. ["Drukarka nie drukuje"]
    mode:   str = "passage",
) -> dict:
    """
    Description:
    Posts a batch to /embed and returns the decoded body, failing on any non-200 so the
    assertions below read as statements about vectors rather than about HTTP.

    Example args:
        client=TestClient(create_app())
        texts=["Drukarka nie drukuje"]
        mode="passage"

    Example result:
        {"vectors": [[0.01, -0.04]], "model": "stub-deterministic", "dimension": 768}
    """
    response = client.post("/embed", json={"texts": texts, "mode": mode})

    assert response.status_code == 200, response.text

    return response.json()


def test_missing_mode_is_rejected(client: TestClient) -> None:
    """Sprawdza, czy `POST /embed` bez pola `mode`, czyli bez trybu liczenia wektorów, dostaje
    status 422.

    Wyłapuje pojawienie się trybu domyślnego: wołający ma podać tryb sam, bo wektory policzone
    w niewłaściwym trybie nie dają błędu, tylko gorsze wyniki wyszukiwania."""
    response = client.post("/embed", json={"texts": [TICKET_TEXT]})

    assert response.status_code == 422


def test_unknown_mode_is_rejected(client: TestClient) -> None:
    """Sprawdza, czy `POST /embed` z trybem spoza trzech dozwolonych (`query`, `passage`, `sts`),
    tu `document`, dostaje status 422.

    Wyłapuje usługę, która przyjmuje dowolny tekst jako tryb: literówka albo nazwa trybu z innego
    modelu przeszłaby wtedy bez błędu."""
    response = client.post("/embed", json={"texts": [TICKET_TEXT], "mode": "document"})

    assert response.status_code == 422


def test_empty_batch_is_rejected(client: TestClient) -> None:
    """Sprawdza, czy `POST /embed` z pustą listą tekstów dostaje status 422.

    Wyłapuje usługę, która na pustą listę odpowiada pustym wynikiem: pusta paczka to błąd po
    stronie wołającego, a odpowiedź 200 by go ukryła."""
    response = client.post("/embed", json={"texts": [], "mode": "passage"})

    assert response.status_code == 422


def test_missing_texts_is_rejected(client: TestClient) -> None:
    """Sprawdza, czy `POST /embed` bez pola `texts` dostaje status 422.

    Wyłapuje pole `texts` z wartością domyślną: żądanie bez tekstów byłoby wtedy traktowane jak
    pusta paczka, a nie jak błędne żądanie."""
    response = client.post("/embed", json={"mode": "passage"})

    assert response.status_code == 422


@pytest.mark.parametrize("mode", ["query", "passage", "sts"])
def test_every_declared_mode_is_accepted(client: TestClient, mode: str) -> None:
    """Sprawdza, czy `POST /embed` przyjmuje każdy z trzech dozwolonych trybów (`query`, `passage`,
    `sts`) i odpowiada statusem 200.

    Wyłapuje usługę, która odrzuca albo nie umie obsłużyć któregoś z własnych trybów, na przykład
    po zmianie ich listy tylko w jednym miejscu."""
    response = client.post("/embed", json={"texts": [TICKET_TEXT], "mode": mode})

    assert response.status_code == 200


def test_batch_preserves_input_order(client: TestClient) -> None:
    """Sprawdza, czy wektory wracają w kolejności tekstów: dla paczki dwóch tekstów pierwszy wektor
    jest taki sam jak dla pierwszego tekstu wysłanego osobno, a drugi jak dla drugiego.

    Wyłapuje usługę, która przestawia wyniki w paczce: wołający przypisuje wektory do tekstów po
    kolejności, więc zgłoszenie dostałoby wektor innego zgłoszenia."""
    body = _embed(client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert body["vectors"][0] == _embed(client, [TICKET_TEXT])["vectors"][0]
    assert body["vectors"][1] == _embed(client, [OTHER_TICKET_TEXT])["vectors"][0]


def test_vector_length_matches_reported_dimension(client: TestClient) -> None:
    """Sprawdza, czy każdy wektor w odpowiedzi `/embed` ma dokładnie tyle liczb, ile usługa podaje
    w polu `dimension`.

    Wyłapuje rozjazd między podanym a faktycznym wymiarem: kto założy kolekcję wektorów według
    tej liczby, dostanie kolekcję, do której wektory nie pasują."""
    body = _embed(client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert all(len(vector) == body["dimension"] for vector in body["vectors"])


def test_vectors_are_unit_length(client: TestClient) -> None:
    """Sprawdza, czy wektor z `/embed` ma długość 1, czyli jest znormalizowany. Test działa
    w procesie, domyślnie na atrapie modelu.

    Wyłapuje wektory nieznormalizowane: wyniki podobieństwa miałyby wtedy inną skalę niż na
    produkcji, więc próg odcięcia wyników znaczyłby w testach co innego."""
    body = _embed(client, [TICKET_TEXT])

    norm = math.sqrt(sum(value * value for value in body["vectors"][0]))

    assert norm == pytest.approx(1.0)


def test_response_names_the_model_that_produced_the_vectors(client: TestClient) -> None:
    """Sprawdza, czy odpowiedź `/embed` podaje niepustą nazwę modelu, który policzył wektory.

    Wyłapuje odpowiedź bez nazwy modelu: kolekcja wektorów jest związana z modelem, a nie tylko
    z wymiarem, więc bez nazwy nie da się stwierdzić, czym wektory policzono."""
    body = _embed(client, [TICKET_TEXT])

    assert body["model"]
