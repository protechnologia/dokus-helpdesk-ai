import os
from collections.abc import Iterator

import httpx2
import pytest

# Integration tests run on the HOST, so they reach a service through a published port — never
# through the compose-internal name from EMBEDDING_BASE_URL (`http://embedder:8000`), which
# resolves only inside the compose network. Hence a test-only variable with a host default.
EMBEDDER_URL_ENV     = "EMBEDDER_TEST_URL"
EMBEDDER_URL_DEFAULT = "http://localhost:8001"


@pytest.fixture
def embedder_client() -> Iterator[httpx2.Client]:
    """
    Description:
    Yields an HTTP client bound to the running `embedder` service. No reachability guard on
    purpose: an unreachable service must fail the test, not skip it — these tests are behind a
    marker, so asking for them means the stack is supposed to be up (CLAUDE.md -> "Testy").

    Example args:
        (none)

    Example result:
        httpx2.Client(base_url="http://localhost:8001")
    """
    base_url = os.environ.get(EMBEDDER_URL_ENV, EMBEDDER_URL_DEFAULT)

    with httpx2.Client(base_url=base_url, timeout=10.0) as client:
        yield client
