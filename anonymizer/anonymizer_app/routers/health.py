from fastapi import APIRouter

from anonymizer_app.models.health_response import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def read_health() -> HealthResponse:
    """
    Description:
    Sonda życia, na którą odpowiada sam proces, niezależnie od silnika: wolny prawdziwy silnik
    nie może sprawić, że zdrowy kontener wygląda na martwy.

    Example args:
        (brak)

    Example result:
        HealthResponse(status="ok")
    """
    return HealthResponse(status="ok")
