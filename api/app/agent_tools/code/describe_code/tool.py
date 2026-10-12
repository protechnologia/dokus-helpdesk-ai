"""
Description:
Prawdziwe narzędzie `describe_code`: oddaje opis projektu z paczki kodu aplikacji, w całości,
razem z gałęzią i dniem budowy paczki. Nie woła embeddera, bazy ani LLM-a — tylko dwa pliki,
które stoją w paczce obok kodu.

    project.md → opis bez komentarzy redakcyjnych
    manifest.json → gałąź i dzień budowy

Przed — wywołanie agenta:

    DescribeCodeQuery()

Po — wynik `describe()` na paczce z aplikacji syntetycznej:

    DescribeCodeResult(
        package_info = CodePackageInfo(branch=None, built_on=date(2026, 10, 12)),
        description  = "Zmyślona aplikacja urzędu na Symfony 1: backend w PHP (akcje modułów…",
    )

O czym pamiętać przy zmianach:

- Opis pisze człowiek i poprawia go bez przebudowy paczki, więc narzędzie czyta plik przy
  każdym wywołaniu, bez pamiętania.
- Opis i metryczkę czyta `CodeDescription` z `core_service/loader_code_description.py`;
  czytnika kodu (`CodePackage`) to narzędzie nie potrzebuje.
- Brak opisu, pusty opis albo brak metryczki to `CodePackageConfigError`, jak brak paczki: nie
  wraca do modelu, zatrzymuje przebieg. Model, który dostałby „paczka nie ma opisu", szukałby
  dalej bez niego, a o braku nikt by się nie dowiedział.
- Czy ścieżki z opisu istnieją w paczce, narzędzie nie sprawdza. Robi to skrypt paczki
  (`scripts/build_code_package.py check-description`), przy budowie i na żądanie.
"""

import logging

from app.agent_tools.code.describe_code.base import DescribeCodeToolBase
from app.agent_tools.code.describe_code.models import DescribeCodeResult
from app.core_service.loader_code_description import CodeDescription

logger = logging.getLogger(__name__)


class DescribeCodeTool(DescribeCodeToolBase):
    """
    Description:
    `describe_code` na prawdziwej paczce kodu: czyta opis projektu i metryczkę, które stoją
    obok kodu.

    Do czego:
    Opis projektu w grafach `search`, `suggest_questions` i `suggest_solution`: mówi modelowi,
    z jakich części składa się aplikacja i w którym katalogu leży kod której z nich, żeby wiedział,
    gdzie spisywać pliki i czego się spodziewać. Tylko do odczytu.

    Flow:
        1. `describe()` bierze opis projektu i metryczkę z czytnika `CodeDescription`.
        2. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        description: CodeDescription,  # np. CodeDescription(Path("/code/data/unsafe/code"))
    ):
        """
        Description:
        Spina narzędzie z opisem projektu i metryczką paczki kodu. Czytnik jest wstrzykiwany,
        nie budowany tutaj.

        Example args:
            description=CodeDescription(Path("/code/data/unsafe/code"))

        Example result:
            DescribeCodeTool gotowe do czytania opisu projektu z paczki
        """
        self._description = description

    async def describe(self) -> DescribeCodeResult:
        """
        Description:
        Czyta z paczki opis projektu w całości oraz gałąź i dzień budowy z metryczki.

        Example args:
            (brak)

        Example result:
            DescribeCodeResult(
                package_info=CodePackageInfo(branch="/main", built_on=date(2026, 10, 7)),
                description="Aplikacja urzędu na Symfony 1: backend w PHP…")

        Raises:
            CodePackageConfigError: w paczce nie ma opisu projektu albo metryczki
        """
        result = DescribeCodeResult(
            package_info = self._description.read_package_info(),
            description  = self._description.read_text(),
        )

        # Sama długość: treść opisu mówi o układzie kodu klienta.
        logger.info("describe_code chars=%d", len(result.description))

        return result
