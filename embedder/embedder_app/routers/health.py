from fastapi import APIRouter

from embedder_app.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def read_health() -> HealthResponse:
    """
    Description:
    Liveness probe answered by the process itself. It must stay independent of the vector
    backend: once real model weights land here (stage 2), a slow first inference must not make
    a healthy container look dead.

    Example args:
        (none)

    Example result:
        HealthResponse(status="ok")
    """
    return HealthResponse(status="ok")
