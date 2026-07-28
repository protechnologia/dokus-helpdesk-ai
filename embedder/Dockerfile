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

# Import root is /code, so `embedder_app.main` resolves the same way here and on the host.
# The package is NOT called `app` like the one in the `api` image: both trees are importable in
# a single pytest process on the host, and two top-level packages of the same name would shadow
# each other (see CLAUDE.md -> "Testy"). Inside the container the name is irrelevant.
COPY embedder_app/ ./embedder_app/

EXPOSE 8000

# No --reload here: live reload is a dev concern and belongs to the compose layer that mounts
# the host code, not to the image we ship.
CMD ["uvicorn", "embedder_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
