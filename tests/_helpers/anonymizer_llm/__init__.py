"""
Description:
Model anonimizujący usługi `anonymizer` w testach: odpowiedź Chat Completions w kształcie
kontraktu (`chat_answer()`), klient modelu na podanej atrapie transportu (`model_client_on()`)
i klient, który odpowiada węzłowi osób i węzłowi adresów tym, co podał test (`scripted_llm()`).
Do testu ewaluacyjnego na żywym modelu: konfiguracja z `.env` ze strażnikiem `-m llm_live`
(`live_agent_settings()`), pomiar silnika `agent` na zestawie (`measure_agent()`), przecieki
ponad próg (`leaks_over_threshold()`) i same progi.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.anonymizer_llm.constants import (
    ADDRESSES_SCHEMA,
    AGENT_MAX_DESTROYED_SAFE,
    AGENT_MAX_DESTROYED_UNSAFE,
    AGENT_MAX_LEAKS_SAFE,
    AGENT_MAX_LEAKS_UNSAFE,
    MODEL_BASE_URL,
    MODEL_NAME,
    PERSONS_SCHEMA,
)
from tests._helpers.anonymizer_llm.helper import (
    chat_answer,
    leaks_over_threshold,
    live_agent_settings,
    measure_agent,
    model_client_on,
    scripted_llm,
)

__all__ = [
    "ADDRESSES_SCHEMA",
    "AGENT_MAX_DESTROYED_SAFE",
    "AGENT_MAX_DESTROYED_UNSAFE",
    "AGENT_MAX_LEAKS_SAFE",
    "AGENT_MAX_LEAKS_UNSAFE",
    "chat_answer",
    "leaks_over_threshold",
    "live_agent_settings",
    "measure_agent",
    "MODEL_BASE_URL",
    "MODEL_NAME",
    "model_client_on",
    "PERSONS_SCHEMA",
    "scripted_llm",
]
