"""
Description:
To, co wspólne dla prawdziwego `describe_code` i jego atrapy: nazwa, klasa argumentów i tekst dla
modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą opis projektu i metryczkę paczki
(`describe()`).

Przed — opis projektu z paczki:

    DescribeCodeResult(
        package_info = CodePackageInfo(branch="/main/stage-gminy", built_on=date(2026, 10, 7)),
        description  = "Aplikacja urzędu na Symfony 1: backend w PHP (kod domenowy w…",
    )

Po — tekst dla modelu:

    {
      "package_info": {
        "branch": "/main/stage-gminy",
        "built_on": "2026-10-07"
      },
      "description": "Aplikacja urzędu na Symfony 1: backend w PHP (kod domenowy w…"
    }

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: opis mówi, GDZIE co leży, nie jak aplikacja się zachowuje, i niczego
  nie cytuje. Źródłem odpowiedzi jest dopiero fragment zacytowany jako przyczyna (`quote_code`).
- Opis wraca w całości i znak w znak, bez skracania: pisze go człowiek i to on pilnuje długości.
- Gałąź paczki bywa nieznana i wtedy `branch` jest `null`, a nie pominięte: model ma zobaczyć,
  że wersji kodu nie da się nazwać.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.code.describe_code.models import DescribeCodeQuery, DescribeCodeResult


class DescribeCodeToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `describe_code`: wszystko poza pobraniem opisu projektu.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeDescribeCodeTool`) i narzędzie właściwe na paczce kodu
    (`DescribeCodeTool`). Każda dokłada wyłącznie `describe()`, więc tekst dla modelu jest ten
    sam w testach i na produkcji.

    Flow:
        1. `run()` woła `describe()` podklasy i dostaje `DescribeCodeResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "describe_code"
    description = read_description(__file__)
    args_model  = DescribeCodeQuery

    @abstractmethod
    async def describe(self) -> DescribeCodeResult:
        """
        Description:
        Pobiera opis projektu w całości i to, z której gałęzi i z kiedy jest kod w paczce.

        Example args:
            (brak)

        Example result:
            DescribeCodeResult(
                package_info=CodePackageInfo(branch="/main", built_on=date(2026, 10, 7)),
                description="Aplikacja urzędu na Symfony 1: backend w PHP…")
        """

    async def run(
        self,
        args: DescribeCodeQuery,  # np. DescribeCodeQuery()
    ) -> str:
        """
        Description:
        Pobiera opis projektu i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=DescribeCodeQuery()

        Example result:
            {"package_info": {"branch": "/main/stage-gminy", "built_on": "2026-10-07"},
             "description": "Aplikacja urzędu na Symfony 1: backend w PHP…"}
        """
        result = await self.describe()
        text   = result_as_json(result)

        return text
