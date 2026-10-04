from collections.abc import Mapping, Sequence

from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.docs.read_docs.base import ReadDocsToolBase
from app.agent_tools.docs.read_docs.errors import UnknownSectionError
from app.agent_tools.docs.read_docs.models import ReadDocsQuery, ReadDocsResult, ReadSection
from app.model.doc_section import DocSection


class FakeReadDocsTool(ReadDocsToolBase):
    """
    Description:
    Atrapa `read_docs`: zamiast bazy oddaje treść ze zmyślonej dokumentacji wspólnej dla
    wszystkich atrap narzędzi dokumentacji (`agent_tools/docs/fake_docs.py`). Inaczej niż atrapy
    wyszukiwań odpowiada NA TO, o co pytano — odczyt po identyfikatorze nie ma „zawsze tego
    samego wyniku".

    Flow:
        1. Test tworzy ją z własnymi sekcjami i treściami albo z zestawem wbudowanym.
        2. Każde `search()` zapisuje zapytanie w `queries` i oddaje żądane sekcje w kolejności
           żądania; nieznany identyfikator kończy się `UnknownSectionError`, bez wyniku częściowego.
        3. `render_for_model()` i `cite()` pochodzą z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        sections: Sequence[DocSection] | None = None,  # np. [DocSection(…)]
        texts:    Mapping[str, str] | None = None,     # np. {"adm-kancelaria-edoreczenia": "…"}
    ):
        """
        Description:
        Ustala dokumentację, z której atrapa czyta, i zakłada dziennik zapytań.

        Example args:
            sections=None
            texts=None

        Example result:
            FakeReadDocsTool czytająca wbudowane cztery sekcje
        """
        sections = list(sections) if sections is not None else default_sections()
        texts    = dict(texts) if texts is not None else default_texts()

        self._items = {
            section.section_id: ReadSection(section=section, text=texts[section.section_id])
            for section in sections
        }

        # Publiczne celowo: testy sprawdzają, które sekcje agent przeczytał.
        self.queries: list[ReadDocsQuery] = []

    async def search(
        self,
        query: ReadDocsQuery,  # np. ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia"])
    ) -> ReadDocsResult:
        """
        Description:
        Zapisuje zapytanie i oddaje żądane sekcje w kolejności żądania.

        Example args:
            query=ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia"])

        Example result:
            ReadDocsResult(items=[ReadSection(section=DocSection(…), text="Uprawnienie…")])

        Raises:
            UnknownSectionError: któregoś identyfikatora nie ma w dokumentacji
        """
        self.queries.append(query)

        # --- wszystko albo nic: brak jednej sekcji unieważnia cały odczyt ---
        unknown = [section_id for section_id in query.section_ids if section_id not in self._items]

        if unknown:
            raise UnknownSectionError(unknown)

        result = ReadDocsResult(
            items = [self._items[section_id] for section_id in query.section_ids],
        )

        return result
