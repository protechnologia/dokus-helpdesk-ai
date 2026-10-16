"""
Description:
Odpowiedź usługi `embedder` w kształcie kontraktu i payload punktu Qdranta z nazwą modelu.
"""

from app.db_qdrant.point.base import EMBEDDING_MODEL_KEY
from tests._helpers.embedding.constants import EMBEDDING_MODEL


def embedder_answer(
    vectors: list[list[float]],       # np. [[0.1, -0.2]]
    model:   str = EMBEDDING_MODEL,   # np. "inny-model"
) -> dict:
    """
    Description:
    Treść odpowiedzi `POST /embed` w kształcie kontraktu usługi `embedder`: wektory i nazwa
    modelu, który je policzył.

    Example args:
        vectors=[[0.1, -0.2]]
        model="model-testowy"

    Example result:
        {"vectors": [[0.1, -0.2]], "model": "model-testowy", "dimension": 2}
    """
    answer = {
        "vectors":   vectors,
        "model":     model,
        "dimension": len(vectors[0]) if vectors else 0,
    }

    return answer


def with_model(
    payload: dict,                    # np. {"ticket_id": "33644"}
    model:   str = EMBEDDING_MODEL,   # np. "inny-model"
) -> dict:
    """
    Description:
    Payload punktu tak, jak leży w Qdrancie: treść punktu i nazwa modelu embeddera, którą każdy
    punkt zapisuje obok niej.

    Example args:
        payload={"ticket_id": "33644"}
        model="model-testowy"

    Example result:
        {"ticket_id": "33644", "embedding_model": "model-testowy"}
    """
    stored = {
        **payload,
        EMBEDDING_MODEL_KEY: model,
    }

    return stored
