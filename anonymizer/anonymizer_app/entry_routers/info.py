from typing import Annotated

from fastapi import APIRouter, Depends

from anonymizer_app.core_engine import Engine, get_engine
from anonymizer_app.core_model.info_response import InfoResponse

router = APIRouter(tags=["info"])

# Przez Annotated, jak w `anonymize.py`: wywołanie w wartości domyślnej linter bierze za zmienny
# domyślny argument.
EngineDep = Annotated[Engine, Depends(get_engine)]


@router.get("/info", response_model=InfoResponse)
async def read_info(
    engine: EngineDep,  # np. AgentEngine(…)
) -> InfoResponse:
    """
    Description:
    Którym silnikiem i z jakim modelem usługa anonimizuje — dla belki frontu przez `GET /instance`
    w `api`. Bez adresu serwera modelu i bez klucza; z modelem się nie łączy, więc odpowiada także
    przy wyłączonym serwerze modelu.

    Example args:
        engine=AgentEngine(…)

    Example result:
        InfoResponse(engine="agent", model="speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic")
    """
    response = InfoResponse(engine=engine.name, model=engine.model)

    return response
