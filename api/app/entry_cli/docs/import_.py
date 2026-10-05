import asyncio
from pathlib import Path

import typer

from app.config import Settings
from app.core_model.doc_import_report import DocsImportReport
from app.core_model.doc_package import DocPackage
from app.core_service.factory_docs_importer import build_docs_importer, docs_index_names
from app.core_service.importer_docs import DocsImportRefused, check_importable
from app.core_service.loader_doc_package import load_doc_package
from app.db_postgres import DbPostgresError
from app.db_qdrant import DbQdrantError
from app.engine_embedding import EmbeddingError
from app.entry_cli.docs.common import print_package

# Plik nazywa się `import_.py`, nie `import.py`: `import` jest słowem kluczowym Pythona i modułu
# o tej nazwie nie da się zaimportować zwykłą instrukcją.

HELP = "Zastąp indeks dokumentacji zawartością paczki (tabela w Postgresie, kolekcja w Qdrancie)."


async def _run(
    package:   DocPackage,  # np. load_doc_package(Path("data/unsafe/instruction"))
    synthetic: bool,        # np. False
) -> DocsImportReport:
    """
    Description:
    Bierze importer z fabryki, uruchamia import i zamyka połączenia — także wtedy, gdy przebieg
    padnie w połowie.

    Example args:
        package=DocPackage(path=Path("data/unsafe/instruction"), directories=[…])
        synthetic=False

    Example result:
        DocsImportReport(documents=2, sections=27, fragments=47, warnings=[])

    Raises:
        DocsImportRefused: paczki nie wolno zaimportować do tego indeksu
        EmbeddingError: embedder nieosiągalny albo odpowiedział błędem
        DbPostgresError: Postgres nieosiągalny albo odrzucił zapis
        DbQdrantError: Qdrant nieosiągalny albo odrzucił zapis
    """
    importer = build_docs_importer(Settings(), synthetic)

    try:
        return await importer.run(package)
    finally:
        await importer.aclose()


def import_package(
    directory: Path = typer.Argument(
        Path("data/unsafe/instruction"), help="Katalog paczki: podkatalog na dokument."
    ),
    synthetic: bool = typer.Option(
        False, "--synthetic", help="Paczka zmyślona: pisz do osobnego indeksu syntetycznego."
    ),
    yes:       bool = typer.Option(False, "--yes", help="Nie pytaj o potwierdzenie."),
) -> None:
    """
    Description:
    `helpdesk docs import` — zastępuje indeks dokumentacji zawartością paczki: tabelę
    w Postgresie i kolekcję w Qdrancie. Po imporcie w indeksie jest dokładnie to, co w paczce.

    Paczka z błędami albo niepasująca do indeksu jest odrzucana przed pytaniem o potwierdzenie
    i przed jakąkolwiek zmianą. Pyta, zanim zastąpi indeks, chyba że podano `--yes`: indeks da
    się odbudować tą samą komendą (zasada 8), ale przebieg na złym katalogu zostawiłby agenta
    z cudzą dokumentacją.

    Example args:
        directory=Path("data/unsafe/instruction")
        synthetic=False
        yes=False

    Example result:
        wypisuje raport paczki i liczby importu; kod 0, gdy indeks został zastąpiony

    Raises:
        typer.Exit: kod 1, gdy paczki nie wolno zaimportować albo operator odmówi; kod 2, gdy
            katalog nie istnieje albo usługa jest nieosiągalna
    """
    # --- wczytanie paczki: bez usług, same pliki ---
    try:
        package = load_doc_package(directory)
    except NotADirectoryError as exc:
        # Kod 2 oddziela „wskazałeś nic" od „paczka jest zepsuta".
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    print_package(package)

    # --- odmowa przed pytaniem: nie ma czego potwierdzać, skoro import i tak by odmówił ---
    try:
        check_importable(package, synthetic)
    except DocsImportRefused as exc:
        # Kod 1, jak przy zepsutej paczce: ponowienie tej samej komendy nic nie zmieni.
        typer.echo(f"\nBŁĄD: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # --- potwierdzenie: pytanie nazywa to, co zniknie ---
    table_name, collection_name = docs_index_names(Settings(), synthetic)
    question = (
        f"\nZastąpić tabelę '{table_name}' i kolekcję '{collection_name}' zawartością {directory}?"
    )

    if not yes and not typer.confirm(question):
        typer.echo("Przerwano.")
        raise typer.Exit(code=1)

    # --- import ---
    try:
        report = asyncio.run(_run(package, synthetic))
    except DocsImportRefused as exc:
        # Ta sama odmowa co wyżej; tutaj tylko wtedy, gdyby sprawdzenia się rozjechały.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (EmbeddingError, DbPostgresError, DbQdrantError) as exc:
        # Leżąca zależność to 2: ponowienie tej samej komendy może zadziałać.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(
        f"\nZaimportowano — dokumentów: {report.documents}, sekcji: {report.sections}, "
        f"fragmentów: {report.fragments} (tabela '{table_name}', kolekcja '{collection_name}')."
    )
