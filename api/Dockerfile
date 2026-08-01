# Tag pins the version, digest pins the exact image: a moving tag would hand a rebuild a
# different base than the one we tested.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

# PYTHONDONTWRITEBYTECODE: no .pyc in the image (and none written into a bind-mounted host tree).
# PYTHONUNBUFFERED: logs reach `docker logs` immediately instead of sitting in a buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Dependencies are copied and installed BEFORE the code: this layer is cached, so editing a .py
# file does not reinstall FastAPI. Reversing the two lines would rebuild the world on every edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Import root is /code, so `app.main` resolves exactly as it does on the host after `pip install -e .`
#
# The image always carries the code, which makes it a self-contained artifact — and prod runs
# exactly this copy. Dev only SHADOWS this path with a bind-mount of ./api/app (live edits, no
# rebuild); the prod compose layer drops that mount and the copy below becomes visible again.
# Consequence: a file missing from this COPY still "works" in dev and breaks in prod.
COPY app/ ./app/

# The `helpdesk` entry point, which on the host comes from `pip install -e .`. The image cannot get
# it that way: pyproject.toml lives in the repo root, outside this build context, and declares
# `package-dir = api` — so installing it here would mean either widening the context to the whole
# repo or duplicating the packaging config. A three-line launcher is the smaller price.
#
# Needed because the batch import of stage 10 runs INSIDE the container, not on a developer's
# host, and `docker compose run api helpdesk …` must simply work.
# PYTHONPATH rather than a bare import: the launcher may be invoked from any working directory,
# and /code lands on sys.path only when it happens to be the current one.
RUN printf '#!/bin/sh\nexec env PYTHONPATH=/code python -c "from app.cli.cli import cli; cli()" "$@"\n' \
      > /usr/local/bin/helpdesk \
 && chmod +x /usr/local/bin/helpdesk

EXPOSE 8000

# No --reload here: live reload is a dev concern and belongs to the compose layer that mounts
# the host code, not to the image we ship.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
