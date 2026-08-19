from collections.abc import Iterator

import httpx2
import pytest

from tests.conftest import api_url, embedder_url

# The addresses themselves live in `tests/conftest.py`, shared with `tests/functional/` — reaching
# a service over its published port is the same problem for both axes.


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
    with httpx2.Client(base_url=embedder_url(), timeout=10.0) as client:
        yield client


@pytest.fixture
def api_client() -> Iterator[httpx2.Client]:
    """
    Description:
    Yields an HTTP client bound to the running `api` service. Like the embedder fixture, it does
    not probe for reachability first: these tests sit behind a marker, so an unreachable service
    is a failure, not a reason to skip (CLAUDE.md -> "Testy").

    Example args:
        (none)

    Example result:
        httpx2.Client(base_url="http://localhost:8010")
    """
    with httpx2.Client(base_url=api_url(), timeout=10.0) as client:
        yield client
