"""
Description:
Klient usługi `anonymizer` na atrapie transportu i odpowiedź usługi w kształcie kontraktu.
"""

import httpx

from app.engine_anonymization import AnonymizationConfigError, Anonymizer, AnonymizerClient
from tests._helpers.anonymization.constants import (
    ANONYMIZED_TEXT,
    BASE_URL,
    FAKE_ENGINE,
    RAW_TEXT,
    REAL_ENGINE,
)
from tests._helpers.transport import always, with_transport


def anonymizer_client_on(
    handler:             httpx.MockTransport,  # np. always(service_answer())
    fake_engine_allowed: bool = False,         # np. True — jak przy atrapie modelu
) -> AnonymizerClient:
    """
    Description:
    Buduje klienta usługi `anonymizer`, który odpowiada z atrapy transportu zamiast z gniazda.
    Bez zgody na atrapę silnika, jak przy prawdziwym modelu, chyba że test poda ją wprost.

    Example args:
        handler=always({"text": "{IMIĘ} …", "engine": "agent"})
        fake_engine_allowed=False

    Example result:
        AnonymizerClient odpowiadający z atrapy
    """
    anonymizer = AnonymizerClient(base_url=BASE_URL, fake_engine_allowed=fake_engine_allowed)
    client     = with_transport(anonymizer, handler)

    return client


async def accepts_the_fake_engine(
    anonymizer: Anonymizer,  # np. build_anonymizer(Settings(llm_generation_provider="fake"))
) -> bool:
    """
    Description:
    Mówi, czy anonimizator przyjmuje wynik atrapy silnika: podstawia mu transport, który zawsze
    odpowiada atrapą, i woła anonimizację raz. Sprawdza zachowanie, a nie pole klienta, więc
    test nie zależy od tego, jak klient pamięta zgodę.

    Example args:
        anonymizer=build_anonymizer(Settings(llm_generation_provider="fake"))

    Example result:
        True — atrapa modelu, więc wynik atrapy silnika wrócił jako tekst
    """
    client = with_transport(anonymizer, always(payload=service_answer(engine=FAKE_ENGINE)))

    try:
        await client.anonymize(RAW_TEXT)
    except AnonymizationConfigError:  # klient odmówił wyniku atrapy
        return False

    return True


def service_answer(
    engine: str = REAL_ENGINE,      # np. "fake"
    text:   str = ANONYMIZED_TEXT,  # np. "{IMIĘ} {NAZWISKO} zgłasza…"
) -> dict[str, str]:
    """
    Description:
    Treść odpowiedzi `POST /anonymize` w kształcie kontraktu usługi.

    Example args:
        engine="fake"
        text="{IMIĘ} {NAZWISKO} zgłasza…"

    Example result:
        {"text": "{IMIĘ} {NAZWISKO} zgłasza…", "engine": "fake"}
    """
    answer = {
        "text":   text,
        "engine": engine,
    }

    return answer
