from collections.abc import Sequence

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.docs.list_docs.base import ListDocsToolBase
from app.agent_tools.docs.list_docs.models import ListDocsResult
from app.core_model.docs.doc_section import DocSection


class FakeListDocsTool(ListDocsToolBase):
    """
    Description:
    Atrapa `list_docs`: zamiast bazy zwraca ustalony spis treści — zmyśloną dokumentację wspólną
    dla wszystkich atrap narzędzi dokumentacji (`agent_tools/docs/fake_docs.py`).

    Flow:
        1. Test tworzy ją z własnymi sekcjami albo z zestawem wbudowanym.
        2. Każde `load()` podbija licznik `calls` i zwraca ten sam spis.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        sections: Sequence[DocSection] | None = None,  # np. [DocSection(…)]
    ):
        """
        Description:
        Ustala spis, który atrapa będzie zwracać, i zeruje licznik wywołań.

        Example args:
            sections=None

        Example result:
            FakeListDocsTool zwracająca wbudowane cztery sekcje przy każdym wywołaniu
        """
        self._result = ListDocsResult(
            sections = list(sections) if sections is not None else default_sections(),
        )

        # Publiczne celowo: testy sprawdzają, czy i ile razy agent sięgnął po spis.
        self.calls = 0

    async def load(self) -> ListDocsResult:
        """
        Description:
        Podbija licznik wywołań i zwraca ustalony spis.

        Example args:
            (brak)

        Example result:
            ListDocsResult(sections=[DocSection(section_id="adm-kancelaria-edoreczenia", …), …])
        """
        self.calls += 1

        return self._result
