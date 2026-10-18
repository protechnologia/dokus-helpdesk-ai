from typing import Annotated

from fastapi import APIRouter, Depends

from anonymizer_app.engine import Engine, get_engine
from anonymizer_app.models.anonymize_request import AnonymizeRequest
from anonymizer_app.models.anonymize_response import AnonymizeResponse

router = APIRouter(tags=["anonymization"])

# Przez Annotated, a nie `engine: Engine = Depends(...)`: wywołanie w wartości domyślnej linter
# bierze za zmienny domyślny argument.
EngineDep = Annotated[Engine, Depends(get_engine)]


@router.post("/anonymize", response_model=AnonymizeResponse)
async def anonymize_text(
    payload: AnonymizeRequest,  # np. AnonymizeRequest(text="Jan Nowak zgłasza…")
    engine:  EngineDep,         # np. FakeEngine()
) -> AnonymizeResponse:
    """
    Description:
    Zamienia dane w tekście na znaczniki i oddaje wynik razem z nazwą silnika. Cienki adapter:
    co jest daną i na jaki znacznik się zamienia, wie silnik, więc jego wymiana nie zmienia tego
    pliku. Wpis w logu robi silnik, bo tylko on wie, który z nich zadziałał.

    Example args:
        payload=AnonymizeRequest(text="Jan Nowak zgłasza, że przesyłki nie przychodzą.")
        engine=FakeEngine()

    Example result:
        AnonymizeResponse(text="Jan Nowak zgłasza, że przesyłki nie przychodzą.", engine="fake")
    """
    text = await engine.anonymize(payload.text)

    response = AnonymizeResponse(text=text, engine=engine.name)

    return response
