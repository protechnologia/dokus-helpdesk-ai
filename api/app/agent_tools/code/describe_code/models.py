from pydantic import BaseModel, ConfigDict, Field

from app.core_model.code.code_package_info import CodePackageInfo


class DescribeCodeQuery(BaseModel):
    """
    Description:
    O co agent prosi `describe_code` — o nic: narzędzie nie ma argumentów i oddaje opis projektu
    w całości. Opis jest krótki i jeden dla całego kodu, więc nie ma czego wybierać.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")


class DescribeCodeResult(BaseModel):
    """
    Description:
    Co daje `describe_code`: opis projektu i to, z której wersji kodu paczka powstała.

    Opis to tekst pisany przez człowieka, w Markdownie: z jakich części składa się aplikacja,
    w którym katalogu leży kod której z nich i czego w paczce nie ma. Gałąź stoi obok, bo kod
    w paczce pochodzi z jednej gałęzi, a instalacja klienta może stać na innej.
    """

    model_config = ConfigDict(extra="forbid")

    package_info: CodePackageInfo
    description:  str = Field(min_length=1, examples=["Aplikacja urzędu na Symfony 1: …"])
