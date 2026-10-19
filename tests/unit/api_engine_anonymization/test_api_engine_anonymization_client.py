import logging

import httpx
import pytest

from app.engine_anonymization import AnonymizationConfigError, AnonymizationError, AnonymizerClient
from tests._helpers.anonymization import (
    ANONYMIZED_TEXT,
    FAKE_ENGINE,
    RAW_TEXT,
    REAL_ENGINE,
    SENSITIVE,
    anonymizer_client_on,
    service_answer,
)
from tests._helpers.transport import always, capturing, raising

# Odpowiedzi usługi, z których klient nie może zrobić tekstu, z opisem przypadku w `id`.
BROKEN_ANSWERS = [
    pytest.param(always(status=503), id="status 503"),
    pytest.param(always(text="<html>proxy error</html>"), id="treść spoza JSON-a"),
    pytest.param(always(payload=["{IMIĘ}"]), id="lista zamiast obiektu"),
    pytest.param(always(payload={"text": ANONYMIZED_TEXT}), id="bez nazwy silnika"),
    pytest.param(always(payload={"engine": REAL_ENGINE}), id="bez tekstu"),
    pytest.param(always(payload=service_answer(text="")), id="pusty tekst"),
    pytest.param(raising(httpx.ConnectError("connection refused")), id="brak połączenia"),
    pytest.param(raising(httpx.ReadTimeout("timed out")), id="przekroczony czas"),
]


@pytest.mark.parametrize("fake_engine_allowed", [False, True], ids=["bez zgody", "ze zgodą"])
async def test_the_text_goes_to_the_service_and_comes_back_anonymized(
    fake_engine_allowed: bool,
) -> None:
    """Sprawdza, czy klient wysyła tekst jednym żądaniem `POST /anonymize` z treścią
    `{"text": …}` i oddaje tekst z odpowiedzi usługi jako `AnonymizedText`, gdy odpowiedział
    silnik inny niż atrapa — tak samo bez zgody na atrapę silnika i z nią.

    Wyłapuje klienta, który zmienia tekst po drodze, pyta inną ścieżkę albo oddaje coś innego niż
    wynik usługi: do modelu poszedłby wtedy tekst, którego anonimizator nie widział. Wyłapuje też
    zgodę na atrapę, która zmienia obsługę prawdziwego silnika."""
    seen: list = []
    client     = anonymizer_client_on(
        capturing(seen, {("POST", "/anonymize"): httpx.Response(200, json=service_answer())}),
        fake_engine_allowed = fake_engine_allowed,
    )

    result = await client.anonymize(RAW_TEXT)

    assert result.text == ANONYMIZED_TEXT
    assert [(call["method"], call["path"], call["body"]) for call in seen] == [
        ("POST", "/anonymize", {"text": RAW_TEXT}),
    ]


async def test_the_fake_engine_is_refused_as_a_config_error() -> None:
    """Sprawdza, czy klient bez zgody na atrapę silnika (tak jak przy prawdziwym modelu) kończy
    odpowiedź usługi działającej na atrapie (`engine: "fake"`) błędem konfiguracji
    `AnonymizationConfigError`, który nazywa `ANONYMIZATION_ENGINE`, zamiast oddać tekst.

    Wyłapuje klienta, który przyjmuje wynik atrapy bez zgody: atrapa oddaje tekst bez zmian, więc
    surowe zgłoszenie poszłoby do modelu zewnętrznego. Wyłapuje też zgłoszenie tego jak chwilowej
    awarii (503), przy której wołający czekałby na coś, czego czekanie nie naprawi."""
    client = anonymizer_client_on(always(payload=service_answer(engine=FAKE_ENGINE, text=RAW_TEXT)))

    with pytest.raises(AnonymizationConfigError, match="ANONYMIZATION_ENGINE"):
        await client.anonymize(RAW_TEXT)


async def test_with_consent_the_fake_engine_result_is_returned() -> None:
    """Sprawdza, czy klient ze zgodą na atrapę silnika (tak jak przy atrapie modelu) oddaje tekst
    z odpowiedzi atrapy, czyli tekst wysłany, bez zmian.

    Wyłapuje klienta, który odmawia atrapy mimo zgody: przy atrapie modelu każda trasa grafu
    kończyłaby się błędem konfiguracji, choć tekst nie trafia wtedy do żadnego modelu."""
    client = anonymizer_client_on(
        always(payload=service_answer(engine=FAKE_ENGINE, text=RAW_TEXT)),
        fake_engine_allowed = True,
    )

    result = await client.anonymize(RAW_TEXT)

    assert result.text == RAW_TEXT


@pytest.mark.parametrize("handler", BROKEN_ANSWERS)
async def test_a_broken_answer_is_an_anonymization_error(handler: httpx.MockTransport) -> None:
    """Sprawdza, czy każda odpowiedź, z której nie da się wziąć tekstu — status spoza 2xx, treść
    spoza JSON-a, lista zamiast obiektu, brak nazwy silnika, brak albo pusty tekst, brak
    połączenia, przekroczony czas — kończy się błędem `AnonymizationError`, który nie jest błędem
    konfiguracji.

    Wyłapuje klienta, który wypuszcza wyjątek `httpx` (reszta aplikacji go nie złapie), oddaje
    niepełny wynik albo zgłasza chwilową awarię usługi jako złą konfigurację."""
    client = anonymizer_client_on(handler)

    with pytest.raises(AnonymizationError) as caught:
        await client.anonymize(RAW_TEXT)

    assert not isinstance(caught.value, AnonymizationConfigError)


@pytest.mark.parametrize(
    "handler",
    [
        *BROKEN_ANSWERS,
        pytest.param(always(service_answer(engine=FAKE_ENGINE, text=RAW_TEXT)), id="atrapa"),
        pytest.param(always(payload={"text": RAW_TEXT}), id="dane w odpowiedzi bez silnika"),
    ],
)
async def test_an_error_message_quotes_no_personal_data(handler: httpx.MockTransport) -> None:
    """Sprawdza, czy komunikat błędu klienta nie zawiera żadnego fragmentu danych osobowych ze
    zgłoszenia (nazwiska, numeru telefonu), także gdy usługa oddała je w odpowiedzi.

    Wyłapuje komunikat, który cytuje wysłany tekst albo treść odpowiedzi: błąd trafia do logu
    usługi `api`, a tekst przed anonimizacją to surowe dane klienta."""
    client = anonymizer_client_on(handler)

    with pytest.raises(AnonymizationError) as caught:
        await client.anonymize(RAW_TEXT)

    assert not [fragment for fragment in SENSITIVE if fragment in str(caught.value)]


async def test_the_log_carries_lengths_and_the_engine_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sprawdza, czy udana anonimizacja zapisuje w logu nazwę silnika i długości tekstów, a na
    żadnym poziomie, także DEBUG, nie zapisuje fragmentu danych osobowych ze zgłoszenia.

    Wyłapuje wpis w logu z treścią zgłoszenia: logi nie są miejscem na dane klienta, a tekst
    przed anonimizacją to dokładnie te dane."""
    client = anonymizer_client_on(always(payload=service_answer()))

    with caplog.at_level(logging.DEBUG):
        await client.anonymize(RAW_TEXT)

    assert f"engine={REAL_ENGINE}" in caplog.text
    assert not [fragment for fragment in SENSITIVE if fragment in caplog.text]


@pytest.mark.parametrize("blank", ["", "   "])
def test_an_empty_address_is_refused_at_build_time(blank: str) -> None:
    """Sprawdza, czy budowa klienta z pustym adresem usługi (pusty tekst albo same spacje) kończy
    się od razu błędem konfiguracji, który nazywa `ANONYMIZATION_BASE_URL`.

    Wyłapuje klienta, który przyjmuje pusty adres: tak compose podstawia brakującą zmienną,
    a pomyłka wyszłaby dopiero przy pierwszym zgłoszeniu, jako niejasny błąd połączenia."""
    with pytest.raises(AnonymizationConfigError, match="ANONYMIZATION_BASE_URL"):
        AnonymizerClient(base_url=blank, fake_engine_allowed=False)


async def test_aclose_closes_the_connections_and_may_be_repeated() -> None:
    """Sprawdza, czy `aclose()` zamyka połączenia klienta i czy drugie wywołanie kończy się
    spokojnie, bez błędu.

    Wyłapuje zamknięcie, które zostawia otwarte połączenia z usługą, albo takie, które pada przy
    powtórzeniu: aplikacja zamyka anonimizator przy wyłączaniu i nie pilnuje, czy już był
    zamknięty."""
    client = anonymizer_client_on(always(payload=service_answer()))

    await client.aclose()
    await client.aclose()

    assert client._client.is_closed
