from fastapi import APIRouter

from app.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def read_health() -> HealthResponse:
    """
    Description:
    Liveness probe. Answers from the process itself — it must not touch Qdrant, the embedder or
    the LLM, otherwise a slow dependency would make a healthy container look dead and compose
    would restart it for no reason.

    Example args:
        (none)

    Example result:
        HealthResponse(status="ok")
    """
    return HealthResponse(status="ok")
