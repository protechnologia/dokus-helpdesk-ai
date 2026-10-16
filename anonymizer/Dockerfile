# Tag przypina wersję, a skrót dokładny obraz: ruchomy tag dałby przy przebudowie inny obraz
# bazowy niż ten, który przetestowaliśmy. Ten sam obraz co w `embedder`.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

# PYTHONDONTWRITEBYTECODE: bez plików .pyc w obrazie i w montowanym drzewie hosta.
# PYTHONUNBUFFERED: logi trafiają do `docker logs` od razu, a nie po zapełnieniu bufora.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Zależności przed kodem: ta warstwa trafia do cache, więc zmiana pliku .py nie instaluje FastAPI
# od nowa.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pakiet nazywa się `anonymizer_app`, a nie `app` jak w obrazie `api`: na hoście wszystkie drzewa
# importuje jeden proces pytest, a dwa pakiety o tej samej nazwie zasłaniałyby się nawzajem.
COPY anonymizer_app/ ./anonymizer_app/

EXPOSE 8000

# Bez --reload: przeładowanie to wygoda deweloperska i należy do warstwy compose, która montuje
# kod z hosta, a nie do obrazu, który wdrażamy.
CMD ["uvicorn", "anonymizer_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
