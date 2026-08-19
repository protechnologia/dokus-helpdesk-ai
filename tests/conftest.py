import os

import pytest

from app.config import Settings

# Where the services answer when a test runs ON THE HOST. The configured values point at
# compose-internal names (`http://embedder:8000`, `http://qdrant:6333`), which resolve only inside
# the compose network — so every host-side test needs these instead. Kept here rather than in each
# file: the same four values were being repeated per test module, and a port changed in one place
# would have left the others pointing at nothing.
#
# In `tests/` root rather than in `tests/integration/`, because `tests/functional/` needs the same
# thing: what separates those two axes is cost and what they prove, not how they reach a service.
EMBEDDER_URL_ENV     = "EMBEDDER_TEST_URL"
EMBEDDER_URL_DEFAULT = "http://localhost:8001"

QDRANT_URL_ENV       = "QDRANT_TEST_URL"
QDRANT_URL_DEFAULT   = "http://localhost:6333"

# Matches DOCKER_API_PORT in .env.example: 8000 is commonly taken by another local project, so the
# base composition publishes 8010 instead.
API_URL_ENV     = "API_TEST_URL"
API_URL_DEFAULT = "http://localhost:8010"


def embedder_url() -> str:
    """
    Description:
    Where the embedder answers from the host.

    Example args:
        (none)

    Example result:
        "http://localhost:8001"
    """
    return os.environ.get(EMBEDDER_URL_ENV, EMBEDDER_URL_DEFAULT)


def qdrant_url() -> str:
    """
    Description:
    Where Qdrant answers from the host.

    Example args:
        (none)

    Example result:
        "http://localhost:6333"
    """
    return os.environ.get(QDRANT_URL_ENV, QDRANT_URL_DEFAULT)


def api_url() -> str:
    """
    Description:
    Where the `api` service answers from the host.

    Example args:
        (none)

    Example result:
        "http://localhost:8010"
    """
    return os.environ.get(API_URL_ENV, API_URL_DEFAULT)


@pytest.fixture
def host_settings() -> Settings:
    """
    Description:
    The application's configuration with the service addresses rewritten for host access.

    Everything else comes from the environment untouched — the LLM provider above all — so a test
    exercises the configuration the product actually runs with, and only the two addresses that
    cannot work outside the compose network are replaced.

    Example args:
        (none)

    Example result:
        Settings(embedding_base_url="http://localhost:8001", qdrant_url="http://localhost:6333", …)
    """
    return Settings(
        embedding_base_url = embedder_url(),
        qdrant_url         = qdrant_url(),
    )
