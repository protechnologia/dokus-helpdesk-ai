"""
Description:
Klient usługi `anonymizer` na atrapie transportu i odpowiedź usługi w kształcie kontraktu.
"""

import httpx

from app.engine_anonymization import AnonymizerClient
from tests._helpers.anonymization.constants import ANONYMIZED_TEXT, BASE_URL, REAL_ENGINE
from tests._helpers.transport import with_transport


def anonymizer_client_on(
    handler: httpx.MockTransport,  # np. always(service_answer())
) -> AnonymizerClient:
    """
    Description:
    Buduje klienta usługi `anonymizer`, który odpowiada z atrapy transportu zamiast z gniazda.

    Example args:
        handler=always({"text": "{IMIĘ} …", "engine": "patterns"})

    Example result:
        AnonymizerClient odpowiadający z atrapy
    """
    client = with_transport(AnonymizerClient(base_url=BASE_URL), handler)

    return client


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
