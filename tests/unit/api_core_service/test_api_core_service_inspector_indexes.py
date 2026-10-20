import json
from datetime import date
from pathlib import Path

import pytest

from app.core_service.loader_code_description import CodeDescription
from app.db_postgres import DbPostgresError
from app.db_qdrant import DbQdrantError
from tests._helpers.instance import (
    counting_postgres,
    counting_qdrant,
    failing_postgres,
    failing_qdrant,
    inspector_on,
    scripted_inspector,
)
from tests._helpers.synthetic_code import synthetic_code_description


async def test_each_index_gets_the_state_of_its_own_count() -> None:
    """Sprawdza, czy raport podaje pięć indeksów w stałej kolejności (karty i wątki zgłoszeń,
    sekcje i fragmenty dokumentacji, paczka kodu), a każdy z liczbą, którą oddała jego własna
    kolekcja, tabela albo metryczka: 171 kart, pusta tabela wątków, brak tabeli dokumentacji,
    7 fragmentów i 30 plików paczki syntetycznej.

    Wyłapuje pomylenie indeksów między sobą (liczba kart pod wątkami, kolekcja dokumentacji
    liczona jako kolekcja kart) i brak tabeli zgłoszony jako zero: belka frontu pokazałaby wtedy
    materiał, którego nie ma, albo pusty indeks jako brakujący."""
    inspector = scripted_inspector(cards=171, threads=0, sections=None, fragments=7)

    report = await inspector.inspect()

    assert [(s.material, s.index, s.count, s.state) for s in report.indexes] == [
        ("tickets", "cards",     171,  "built"),
        ("tickets", "threads",   0,    "empty"),
        ("docs",    "sections",  None, "missing"),
        ("docs",    "fragments", 7,    "built"),
        ("code",    "package",   30,   "built"),
    ]


async def test_the_code_package_carries_its_branch_and_build_day() -> None:
    """Sprawdza, czy raport niesie gałąź i dzień budowy paczki kodu z jej metryczki — dla paczki
    syntetycznej: bez gałęzi, z dniem budowy z pliku `manifest.json`.

    Wyłapuje raport bez wersji kodu: odpowiedź z kodu opisuje tylko gałąź, z której zbudowano
    paczkę, więc belka musi ją pokazać."""
    expected = synthetic_code_description().read_package_info()

    report = await scripted_inspector().inspect()

    assert report.code_package == expected


@pytest.mark.parametrize(
    "files",
    [{}, {"manifest.json": {"branch": "/main", "built_on": "2026-10-07", "package": {"files": 3}}}],
    ids=["pusty katalog", "metryczka bez opisu projektu"],
)
async def test_a_package_without_its_manifest_or_description_is_missing(
    tmp_path: Path,
    files:    dict[str, object],  # wstrzykiwane przez pytest z listy w dekoratorze wyżej
) -> None:
    """Sprawdza, czy paczka kodu bez metryczki albo z metryczką, ale bez opisu projektu, ma w
    raporcie stan „missing", bez liczby plików i bez gałęzi, a pozostałe indeksy liczą się dalej.

    Wyłapuje paczkę uznaną za zbudowaną, choć narzędzia kodu skończyłyby się na niej błędem
    konfiguracji (`describe_code` bez opisu, każde narzędzie bez metryczki), i brak paczki, który
    przerywa cały raport zamiast stać w nim jako stan."""
    for name, content in files.items():
        (tmp_path / name).write_text(json.dumps(content), encoding="utf-8")

    inspector = scripted_inspector(cards=171, code=CodeDescription(tmp_path))

    report = await inspector.inspect()
    code   = report.indexes[-1]

    assert (code.index, code.count, code.state) == ("package", None, "missing")
    assert report.code_package is None
    assert report.indexes[0].count == 171


async def test_a_package_with_manifest_and_description_is_built(tmp_path: Path) -> None:
    """Sprawdza, czy paczka z metryczką i opisem projektu w katalogu tymczasowym ma w raporcie
    liczbę plików z metryczki (3), gałąź i dzień budowy — bez kodu w `repo/`.

    Wyłapuje liczbę plików liczoną na dysku zamiast wziętej z metryczki albo gałąź z innego
    pola: belka pokazywałaby nie to, co zapisał skrypt paczki."""
    manifest = {"branch": "/main", "built_on": "2026-10-07", "package": {"files": 3}}

    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "project.md").write_text("Opis projektu.", encoding="utf-8")

    report = await scripted_inspector(code=CodeDescription(tmp_path)).inspect()

    assert report.indexes[-1].count == 3
    assert (report.code_package.branch, report.code_package.built_on) == (
        "/main",
        date(2026, 10, 7),
    )


async def test_a_qdrant_failure_is_an_error_not_a_missing_collection() -> None:
    """Sprawdza, czy Qdrant odpowiadający błędem 500 kończy raport błędem `DbQdrantError`,
    a nie stanem „missing".

    Wyłapuje awarię bazy przemilczaną jako brak indeksu: belka mówiłaby „nie zbudowano", choć
    indeks jest, a Qdrant chwilowo nie odpowiada — trasa ma wtedy oddać 503."""
    inspector = inspector_on(
        qdrant   = failing_qdrant(),
        threads  = counting_postgres(0),
        sections = counting_postgres(0),
        code     = synthetic_code_description(),
    )

    with pytest.raises(DbQdrantError):
        await inspector.inspect()


async def test_a_postgres_failure_is_an_error_not_a_missing_table() -> None:
    """Sprawdza, czy awaria Postgresa przy liczeniu wierszy kończy raport błędem
    `DbPostgresError`, a nie stanem „missing".

    Wyłapuje łapanie każdego błędu bazy jak braku tabeli: niedziałająca baza wyglądałaby na
    belce jak niezbudowany indeks."""
    inspector = inspector_on(
        qdrant   = counting_qdrant(cards=1, fragments=1),
        threads  = failing_postgres(),
        sections = counting_postgres(0),
        code     = synthetic_code_description(),
    )

    with pytest.raises(DbPostgresError):
        await inspector.inspect()


async def test_aclose_closes_the_clients_of_every_index() -> None:
    """Sprawdza, czy zamknięcie serwisu zamyka klienta Qdranta i oba klienty Postgresa, na
    których stoją kolekcje i tabele.

    Wyłapuje serwis, który przy wyłączaniu aplikacji zostawia otwartą pulę połączeń Postgresa
    albo połączenia HTTP do Qdranta."""
    qdrant   = counting_qdrant(cards=1, fragments=1)
    threads  = counting_postgres(0)
    sections = counting_postgres(0)

    inspector = inspector_on(qdrant, threads, sections, synthetic_code_description())

    await inspector.aclose()

    assert qdrant._client.is_closed
    assert (threads.closed, sections.closed) == (True, True)
