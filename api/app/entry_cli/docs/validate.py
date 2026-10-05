from pathlib import Path

import typer

from app.core_service.loader_doc_package import load_doc_package
from app.entry_cli.docs.common import print_package

HELP = "Sprawdź paczkę dokumentacji: manifesty wobec plików sekcji."


def validate_package(
    directory: Path = typer.Argument(
        Path("data/unsafe/instruction"), help="Katalog paczki: podkatalog na dokument."
    ),
) -> None:
    """
    Description:
    `helpdesk docs validate` — czyta paczkę dokumentacji i kończy się kodem niezerowym, gdy coś
    się w niej nie zgadza, więc komenda działa jako bramka przed importem. Żadnej usługi nie
    woła: sprawdza wyłącznie pliki.

    Cienki adapter nad `load_doc_package()` — tego samego wczytania używa `helpdesk docs import`,
    więc paczka, która tu przechodzi, nie zostanie tam odrzucona za błędy.

    Example args:
        directory=Path("data/unsafe/instruction")

    Example result:
        wypisuje raport; kod 0, gdy paczka jest bez błędów (ostrzeżenia go nie zmieniają)

    Raises:
        typer.Exit: kod 1 przy błędach w paczce, kod 2, gdy katalog nie istnieje
    """
    try:
        package = load_doc_package(directory)
    except NotADirectoryError as exc:
        # Kod 2 oddziela „wskazałeś nic" od „paczka jest zepsuta".
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    print_package(package)

    if not package.ok:
        raise typer.Exit(code=1)
