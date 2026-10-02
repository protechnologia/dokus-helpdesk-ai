from fastapi import APIRouter

from app.routers.health.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def read_health() -> HealthResponse:
    """
    Description:
    Sonda żywotności. Odpowiada z samego procesu — nie może dotykać Qdranta, embeddera ani LLM-a,
    bo wolna zależność sprawiłaby, że zdrowy kontener wygląda na martwy, a compose restartowałby
    go bez powodu.

    Example args:
        (brak)

    Example result:
        HealthResponse(status="ok")
    """
    return HealthResponse(status="ok")
