from app.agent_tools.code.describe_code.base import DescribeCodeToolBase
from app.agent_tools.code.describe_code.models import DescribeCodeResult
from app.agent_tools.code.fake_code import PROJECT_DESCRIPTION, default_package_info
from app.core_model.code.code_package_info import CodePackageInfo


class FakeDescribeCodeTool(DescribeCodeToolBase):
    """
    Description:
    Atrapa `describe_code`: zamiast paczki na dysku zwraca ustalony opis projektu — zmyślony,
    wspólny dla atrap narzędzi kodu (`agent_tools/code/fake_code.py`) — zawsze ten sam.

    Flow:
        1. Test tworzy ją z własnym opisem i metryczką albo z zestawem wbudowanym.
        2. Każde `describe()` podbija licznik `calls` i zwraca ten sam wynik.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        description:  str | None             = None,  # np. "Aplikacja bez opisanych katalogów."
        package_info: CodePackageInfo | None = None,  # np. CodePackageInfo(branch="/main", …)
    ):
        """
        Description:
        Ustala opis i metryczkę, które atrapa będzie zwracać, i zeruje licznik wywołań.

        Example args:
            description=None
            package_info=None

        Example result:
            FakeDescribeCodeTool zwracająca wbudowany opis zmyślonej aplikacji, bez gałęzi
        """
        self._result = DescribeCodeResult(
            package_info = package_info if package_info is not None else default_package_info(),
            description  = description if description is not None else PROJECT_DESCRIPTION,
        )

        # Publiczne celowo: testy sprawdzają, czy i ile razy agent sięgnął po opis.
        self.calls = 0

    async def describe(self) -> DescribeCodeResult:
        """
        Description:
        Podbija licznik wywołań i zwraca ustalony opis.

        Example args:
            (brak)

        Example result:
            DescribeCodeResult(
                package_info=CodePackageInfo(branch=None, built_on=date(2026, 10, 1)),
                description="Zmyślona aplikacja urzędu na Symfony 1: backend w PHP…")
        """
        self.calls += 1

        return self._result
