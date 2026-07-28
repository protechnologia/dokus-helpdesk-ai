from typing import Annotated

from fastapi import APIRouter, Depends

from embedder_app.encoding import Encoder, get_encoder
from embedder_app.models import EmbedRequest, EmbedResponse

router = APIRouter(tags=["embedding"])

# Injected through Annotated rather than `encoder: Encoder = Depends(...)`: a call in a default
# argument is evaluated once at import time for every other library, so linters flag it — the
# Annotated form says "dependency" without looking like a mutable default.
EncoderDep = Annotated[Encoder, Depends(get_encoder)]


@router.post("/embed", response_model=EmbedResponse)
async def create_embeddings(
    payload: EmbedRequest,  # e.g. EmbedRequest(texts=["Brak tonera"], mode="passage")
    encoder: EncoderDep,    # e.g. FakeEncoder(dimension=768)
) -> EmbedResponse:
    """
    Description:
    Embeds a batch of texts in one mode and returns the vectors in the order they were sent.
    A thin adapter: what a mode means, how wide the vectors are and what the model is called are
    answered by the encoder, so swapping the backend changes nothing in this file. Logging lives
    in the encoder too — it is the only layer that knows which model actually ran.

    Example args:
        payload=EmbedRequest(texts=["Drukarka nie drukuje"], mode="passage")
        encoder=FakeEncoder(dimension=768)

    Example result:
        EmbedResponse(vectors=[[0.01, -0.04, …]], model="fake", dimension=768)
    """
    vectors = await encoder.encode(payload.texts, payload.mode)

    return EmbedResponse(
        vectors   = vectors,
        model     = encoder.model_name,
        dimension = encoder.dimension,
    )
