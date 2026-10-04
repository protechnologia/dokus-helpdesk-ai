"""
Description:
To, co wspólne dla punktów obu materiałów: identyfikator punktu liczony z identyfikatora
źródłowego i odczyt nazwanego wektora z punktu oddanego przez Qdranta.

O czym pamiętać przy zmianach:

- `POINT_ID_NAMESPACE` jest ZAMROŻONY. Jego zmiana rozsypuje wszystkie identyfikatory naraz, więc
  następna indeksacja zdublowałaby korpus, zamiast go nadpisać. Pilnuje tego test złotej wartości.
- Namespace jest jeden dla zgłoszeń i dokumentacji: identyfikator punktu jest unikalny w obrębie
  kolekcji, a te materiały leżą w osobnych kolekcjach.
"""

import uuid

from app.db_qdrant.errors import DbQdrantConfigError

# Qdrant przyjmuje jako identyfikator punktu tylko liczbę bez znaku albo UUID, a nasze
# identyfikatory to teksty („33644", „adm-kancelaria-edoreczenia"). UUID5, a nie licznik, bo
# odwzorowanie musi być FUNKCJĄ identyfikatora: dwa przebiegi indeksacji trafiają w te same punkty.
POINT_ID_NAMESPACE = uuid.UUID("6f1d5a3c-6b8e-5e2a-9a44-0f2c6f9c1b77")


def point_id_for(
    source_id: str,  # np. "33644" albo "adm-kancelaria-edoreczenia"
) -> str:
    """
    Description:
    Zamienia identyfikator źródłowy — numer zgłoszenia albo identyfikator sekcji — na UUID,
    którego wymaga Qdrant. Ten sam identyfikator daje zawsze ten sam punkt, więc ponowna
    indeksacja nadpisuje, a odczyt po identyfikatorze nie potrzebuje wyszukiwania.

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
