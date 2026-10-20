from pydantic import BaseModel, ConfigDict, Field

from app.core_model.code.code_package_info import CodePackageInfo
from app.core_model.instance.index_status import IndexStatus


class IndexReport(BaseModel):
    """
    Description:
    Stan wszystkich indeksów, na których stoją narzędzia agenta, i to, z której gałęzi jest
    paczka kodu. Wynik `IndexInspector.inspect()` z `core_service/inspector_indexes.py`.

    Do czego:
    Na tym stoi trasa `GET /instance`: front pokazuje na belce, które materiały są zbudowane,
    a które puste. Gałąź i dzień budowy paczki stoją osobno od jej stanu, bo odpowiedź z kodu
    opisuje tylko tę gałąź; `code_package` to `None`, gdy paczki nie ma.
    """

    model_config = ConfigDict(extra="forbid")

    indexes:      list[IndexStatus]      = Field(examples=[[]])
    code_package: CodePackageInfo | None = Field(examples=[None])
