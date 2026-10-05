import typer

from app.core_model.docs.doc_directory import DocDirectory
from app.core_model.docs.doc_package import DocPackage

# Wspólne dla `docs validate` i `docs index`: obie wypisują to samo o wczytanej paczce.


def _describe(
    directory: DocDirectory,  # np. DocDirectory(path=…/instrukcja-administratora, manifest=…)
) -> str:
    """
    Description:
    Składa jedną linię o poprawnym katalogu: dokument, wydanie, liczba sekcji i dopisek, gdy
    dokument jest zmyślony.

    Example args:
        directory=DocDirectory(path=Path("…/instrukcja-administratora"), manifest=DocManifest(…))

    Example result:
        "instrukcja-administratora — Instrukcja administratora 4.12, sekcji: 13 (syntetyczny)"
    """
    manifest  = directory.manifest
    synthetic = " (syntetyczny)" if manifest.synthetic else ""

    line = (
        f"{directory.path.name} — {manifest.document} {manifest.version}, "
        f"sekcji: {len(manifest.sections)}{synthetic}"
    )

    return line


def print_package(
    package: DocPackage,  # np. load_doc_package(Path("data/unsafe/instruction"))
) -> None:
    """
    Description:
    Wypisuje wczytaną paczkę: linię na dokument, pod nią jego błędy i ostrzeżenia, na końcu
    błędy całej paczki i podsumowanie.

    Example args:
        package=DocPackage(path=Path("data/safe/instruction"), directories=[…])

    Example result:
        None — raport na stdout
    """
    for directory in package.directories:
        # --- katalog z błędami: bez opisu, bo manifestu mogło nie dać się przeczytać ---
        if not directory.ok:
            typer.echo(f"BŁĄD {directory.path.name}")

            for error in directory.errors:
                typer.echo(f"       {error}")
        # --- katalog poprawny ---
        else:
            typer.echo(f"OK   {_describe(directory)}")

        # Ostrzeżenie niczego nie wstrzymuje, ale operator ma je zobaczyć przy swoim dokumencie.
        for warning in directory.warnings:
            typer.echo(f"       UWAGA: {warning}")

    # --- to, czego nie widać w jednym katalogu ---
    for error in package.errors:
        typer.echo(f"BŁĄD {error}")

    errors = sum(len(directory.errors) for directory in package.directories) + len(package.errors)

    typer.echo(
        f"\nDokumentów: {len(package.directories)}, sekcji: {package.section_count}, "
        f"błędów: {errors}, ostrzeżeń: {len(package.warnings)}."
    )
