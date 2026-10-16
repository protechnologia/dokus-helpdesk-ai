"""
Description:
To, co wspólne dla punktów obu materiałów: identyfikator punktu liczony z identyfikatora
źródłowego, odczyt nazwanego wektora z punktu oddanego przez Qdranta i nazwa modelu embeddera
w payloadzie.

O czym pamiętać przy zmianach:

- `POINT_ID_NAMESPACE` jest ZAMROŻONY. Jego zmiana rozsypuje wszystkie identyfikatory naraz, więc
  następna indeksacja zdublowałaby korpus, zamiast go nadpisać. Pilnuje tego test złotej wartości.
- Namespace jest jeden dla zgłoszeń i dokumentacji: identyfikator punktu jest unikalny w obrębie
  kolekcji, a te materiały leżą w osobnych kolekcjach.
- Każdy punkt niesie w payloadzie nazwę modelu embeddera (`EMBEDDING_MODEL_KEY`). Zapisują ją
  punkty, sprawdza kolekcja, a z treści punktu wycina `payload_without_model()`.
"""

import uuid

from app.db_qdrant.errors import DbQdrantConfigError

# Klucz payloadu z nazwą modelu embeddera, który policzył wektory punktu. Stoi w payloadzie
# KAŻDEGO punktu, bo Qdrant 1.12 nie ma miejsca na metadane kolekcji; wektory dwóch modeli nie są
# porównywalne, nawet przy tym samym wymiarze, a bez nazwy nie da się tego sprawdzić.
EMBEDDING_MODEL_KEY = "embedding_model"

# Qdrant przyjmuje jako identyfikator punktu tylko liczbę bez znaku albo UUID, a nasze
# identyfikatory to teksty („33644", „adm-kancelaria-edoreczenia"). UUID5, a nie licznik, bo
# odwzorowanie musi być FUNKCJĄ identyfikatora: dwa przebiegi indeksacji trafiają w te same punkty.
POINT_ID_NAMESPACE = uuid.UUID("6f1d5a3c-6b8e-5e2a-9a44-0f2c6f9c1b77")


def point_id_for(
    source_id: str,  # np. "33644" albo "adm-kancelaria-edoreczenia#0"
) -> str:
    """
    Description:
    Zamienia identyfikator źródłowy — numer zgłoszenia albo identyfikator sekcji z numerem
    fragmentu — na UUID, którego wymaga Qdrant. Ten sam identyfikator daje zawsze ten sam punkt,
    więc ponowna indeksacja nadpisuje, a odczyt po identyfikatorze nie potrzebuje wyszukiwania.

    Example args:
        source_id="33644"

    Example result:
        "df3b51f3-9eac-56f3-9f28-6253f23dd731"
    """
    return str(uuid.uuid5(POINT_ID_NAMESPACE, source_id))


def named_vector(
    entry: dict,  # np. {"id": "df3b…", "vector": {"problem": [0.5, 0.5]}, "payload": {…}}
    name:  str,   # np. "problem"
) -> list[float]:
    """
    Description:
    Wyjmuje z punktu oddanego przez Qdranta wektor o podanej nazwie. Punkt bez niego pochodzi
    z kolekcji zbudowanej w innym układzie — czekanie tego nie naprawi.

    Example args:
        entry={"id": "df3b51f3-…", "vector": {"problem": [0.5, 0.5], "sts": [0.5, -0.5]}}
        name="problem"

    Example result:
        [0.5, 0.5]

    Raises:
        DbQdrantConfigError: punkt nie ma wektora o tej nazwie
    """
    vectors = entry.get("vector")
    vector  = vectors.get(name) if isinstance(vectors, dict) else None

    if not isinstance(vector, list):
        raise DbQdrantConfigError(
            f"punkt {entry.get('id')!r} nie ma wektora '{name}' — kolekcję zbudowano w innym "
            f"układzie; skasuj ją i odbuduj z plików"
        )

    return vector


def embedding_model_of(
    entry: dict,  # np. {"id": "df3b…", "payload": {"ticket_id": "33644", "embedding_model": "…"}}
) -> str:
    """
    Description:
    Wyjmuje z punktu albo trafienia oddanego przez Qdranta nazwę modelu embeddera, który
    policzył jego wektory. Punkt bez niej pochodzi z kolekcji zbudowanej przed zapisem modelu —
    czekanie tego nie naprawi, więc to błąd konfiguracji, jak brak nazwanego wektora.

    Example args:
        entry={"id": "df3b51f3-…", "payload": {"ticket_id": "33644",
                                               "embedding_model": "OPI-PIB/PolDense-150M"}}

    Example result:
        "OPI-PIB/PolDense-150M"

    Raises:
        DbQdrantConfigError: payload punktu nie ma nazwy modelu
    """
    payload = entry.get("payload")
    model   = payload.get(EMBEDDING_MODEL_KEY) if isinstance(payload, dict) else None

    if not isinstance(model, str) or not model:
        raise DbQdrantConfigError(
            f"punkt {entry.get('id')!r} nie ma zapisanego modelu embeddera — kolekcję "
            f"zbudowano przed zapisem modelu; skasuj ją i odbuduj z plików"
        )

    return model


def payload_without_model(
    entry: dict,  # np. {"id": "df3b…", "payload": {"ticket_id": "33644", "embedding_model": "…"}}
) -> dict:
    """
    Description:
    Oddaje payload punktu oddanego przez Qdranta bez nazwy modelu, czyli to, co punkt zapisał
    jako swoją treść: kartę zgłoszenia albo opis sekcji. Nazwa modelu nie należy do karty, a
    karta odrzuca klucze spoza kontraktu.

    Example args:
        entry={"id": "df3b51f3-…", "payload": {"ticket_id": "33644", "embedding_model": "…"}}

    Example result:
        {"ticket_id": "33644"}
    """
    payload  = entry.get("payload") or {}
    stripped = {key: value for key, value in payload.items() if key != EMBEDDING_MODEL_KEY}

    return stripped
