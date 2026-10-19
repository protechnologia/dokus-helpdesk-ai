"""
Description:
Model anonimizujący usługi `anonymizer` w testach: odpowiedź Chat Completions w kształcie
kontraktu i klient modelu na atrapie transportu, który odpowiada węzłowi osób i węzłowi adresów
tym, co podał test. Rozpoznaje węzeł po nazwie schematu w żądaniu (`response_format`), więc oba
węzły mogą pytać ten sam klient równolegle, jak w grafie.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest

from anonymizer_app.config import Settings
from anonymizer_app.core_engine import build_engine
from anonymizer_app.engine_llm import LLMClient
from tests._helpers.anonymizer_llm.constants import (
    ADDRESSES_SCHEMA,
    MODEL_BASE_URL,
    MODEL_NAME,
    PERSONS_SCHEMA,
)
from tests._helpers.golden_anonymization import (
    AnonymizationMeasurement,
    anonymization_set,
    measure_anonymization,
)
from tests._helpers.live import LLM_LIVE_MARKER
from tests._helpers.transport import with_transport


def chat_answer(
    content:           str,           # np. '{"adresy": []}'
    finish_reason:     str = "stop",  # np. "length" — odpowiedź ucięta limitem
    prompt_tokens:     int = 100,     # np. 1840
    completion_tokens: int = 10,      # np. 32
) -> dict[str, Any]:
    """
    Description:
    Treść odpowiedzi serwera Chat Completions w kształcie, w jakim oddaje ją vLLM.

    Example args:
        content='{"adresy": []}'
        finish_reason="stop"

    Example result:
        {"choices": [{"message": {"role": "assistant", "content": '{"adresy": []}'},
                      "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    """
    answer = {
        "choices": [
            {
                "message":       {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            },
        ],
        "usage":   {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }

    return answer


def scripted_llm(
    persons:   Sequence[dict[str, str]] = (),  # np. [{"tekst": "Nowak", "rodzaj": "NAZWISKO"}]
    addresses: Sequence[str]            = (),  # np. ["Wierzbowa 6"]
    seen:      list | None              = None,  # wypełniana w miejscu: treść każdego żądania
) -> LLMClient:
    """
    Description:
    Klient modelu, którego atrapa transportu odpowiada na każde wywołanie węzła osób listą
    `persons`, a węzła adresów — listą `addresses`. Każde żądanie, z treścią jako słownikiem,
    trafia do `seen`, gdy ją podano.

    Example args:
        persons=[{"tekst": "Jan", "rodzaj": "IMIĘ"}, {"tekst": "Nowak", "rodzaj": "NAZWISKO"}]
        addresses=[]
        seen=[]

    Example result:
        LLMClient, który na pytanie o osoby oddaje '{"dane": [{"tekst": "Jan", …}, …]}'
    """
    contents = {
        PERSONS_SCHEMA:   json.dumps({"dane": list(persons)}, ensure_ascii=False),
        ADDRESSES_SCHEMA: json.dumps({"adresy": list(addresses)}, ensure_ascii=False),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)

        if seen is not None:
            seen.append(body)

        schema = body["response_format"]["json_schema"]["name"]

        return httpx.Response(200, json=chat_answer(contents[schema]))

    return model_client_on(httpx.MockTransport(handler))


def model_client_on(
    transport: httpx.MockTransport,  # np. always(chat_answer('{"adresy": []}'))
) -> LLMClient:
    """
    Description:
    Klient modelu z adresem i nazwą testową, rozmawiający z podaną atrapą transportu.

    Example args:
        transport=always(chat_answer('{"adresy": []}'))

    Example result:
        LLMClient(base_url="http://model:8000/v1", model="test-model") na atrapie transportu
    """
    client = LLMClient(base_url=MODEL_BASE_URL, model=MODEL_NAME)

    return with_transport(client, transport)


def live_agent_settings(
    config: pytest.Config,  # np. request.config
) -> Settings:
    """
    Description:
    Konfiguracja silnika `agent` dla testów na żywym modelu anonimizującym, z pliku `.env`
    dewelopera (usługa sama `.env` nie czyta, więc test podaje go wprost). Odmawia błędem, nie
    pominięciem, gdy testy wybrano bez jawnego `llm_live` albo gdy w `.env` nie ma adresu
    i nazwy modelu.

    Example args:
        config=request.config

    Example result:
        Settings(anonymization_engine="agent", llm_anonymization_base_url="https://…/v1", …)

    Raises:
        AssertionError: wybór testów nie wymienia `llm_live` albo brakuje adresu lub modelu
    """
    selected = config.getoption("markexpr")

    assert LLM_LIVE_MARKER in selected, (
        f"testy na żywym modelu uruchamia się jawnie: -m {LLM_LIVE_MARKER} (wybrano -m "
        f"{selected!r})"
    )

    settings = Settings(_env_file=".env", anonymization_engine="agent")

    assert settings.llm_anonymization_base_url and settings.llm_anonymization_model, (
        "silnik `agent` wymaga modelu anonimizującego — ustaw LLM_ANONYMIZATION_BASE_URL "
        "i LLM_ANONYMIZATION_MODEL w .env"
    )

    return settings


async def measure_agent(
    path:     Path,      # np. SAFE_FILE
    settings: Settings,  # np. live_agent_settings(request.config)
) -> AnonymizationMeasurement:
    """
    Description:
    Mierzy silnik `agent` na zestawie golden setu, po kolei, jak przy zwykłej pracy usługi. Silnik
    powstaje i zamyka się w tym samym przebiegu pętli zdarzeń, bo jego klient `httpx` jest z nią
    związany.

    Example args:
        path=SAFE_FILE
        settings=live_agent_settings(request.config)

    Example result:
        AnonymizationMeasurement(outcomes=(…), leaks={"IMIĘ": KindCount(found=0, total=27), …}, …)
    """
    engine = build_engine(settings)

    try:
        measurement = await measure_anonymization(anonymization_set(path), engine.anonymize)
    finally:
        await engine.aclose()

    return measurement


def leaks_over_threshold(
    measurement: AnonymizationMeasurement,  # np. pomiar zestawu zmyślonego
    max_leaks:   Mapping[str, int],         # np. AGENT_MAX_LEAKS_UNSAFE
) -> dict[str, str]:
    """
    Description:
    Rodzaje danych — wszystkie, także imiona i nazwiska — w których przecieków jest więcej, niż
    pozwala próg; rodzaj bez progu ma próg zero.

    Example args:
        measurement=AnonymizationMeasurement(leaks={"IMIĘ": KindCount(found=2, total=50), …}, …)
        max_leaks={"IMIĘ": 1}

    Example result:
        {"IMIĘ": "2 z 50 (próg 1)"}
    """
    over = {
        kind: f"{count.found} z {count.total} (próg {max_leaks.get(kind, 0)})"
        for kind, count in measurement.leaks.items()
        if count.found > max_leaks.get(kind, 0)
    }

    return over
