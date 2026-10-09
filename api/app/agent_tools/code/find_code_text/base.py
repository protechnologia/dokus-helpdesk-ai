"""
Description:
To, co wspólne dla prawdziwego `find_code_text` i jego atrapy: nazwa, klasa argumentów, tekst dla
modelu i przycinanie treści linii. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą wynik
(`find()`).

Przed — wynik szukania:

    FindCodeTextResult(
        lines = [
            MatchedLine(
                path       = "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                line       = 9,
                matched_by = "exact",
                text       = "throw new BrakSekwencjiException('Brak sekwencji numeracji dla…",
            ),
        ],
        omitted_over_limit = 0,
    )

Po — tekst dla modelu:

    {
      "lines": [
        {
          "path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
          "line": 9,
          "matched_by": "exact",
          "text": "throw new BrakSekwencjiException('Brak sekwencji numeracji dla…"
        }
      ],
      "omitted_over_limit": 0
    }

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: niczego nie cytuje. Źródłem odpowiedzi jest dopiero fragment
  zacytowany jako przyczyna narzędziem `quote_code`.
- Wynik niesie treść linii, inaczej niż wyszukiwania zgłoszeń i dokumentacji. Tam treść bez
  odczytu byłaby treścią bez źródła; w kodzie źródła nie tworzy ani szukanie, ani odczyt.
- `matched_by` nosi nazwę pola, którym agent pytał: `exact` albo `words`.
- Ścieżka i numer linii są te same, które przyjmuje `quote_code`.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.code.find_code_text.models import (
    MAX_TEXT_CHARS,
    FindCodeTextQuery,
    FindCodeTextResult,
)

# Tym znakiem kończy się treść linii, która nie zmieściła się w wyniku.
CUT_MARK = "…"


def shorten_line(
    text: str,  # np. "            throw new BrakSekwencjiException('Brak sekwencji…');"
) -> str:
    """
    Description:
    Przygotowuje treść linii kodu do pokazania modelowi: zdejmuje wcięcie, a linię dłuższą niż
    `MAX_TEXT_CHARS` ucina i kończy znakiem „…", żeby model nie wziął ucięcia za koniec linii.
    Wspólne dla narzędzia i atrapy, więc w testach i na produkcji treść wygląda tak samo.

    Example args:
        text="            throw new BrakSekwencjiException('Brak sekwencji numeracji');"

    Example result:
        "throw new BrakSekwencjiException('Brak sekwencji numeracji');"
    """
    stripped = text.strip()

    if len(stripped) <= MAX_TEXT_CHARS:
        return stripped

    return stripped[:MAX_TEXT_CHARS] + CUT_MARK


class FindCodeTextToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `find_code_text`: wszystko poza samym szukaniem.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeFindCodeTextTool`) i narzędzie właściwe na paczce kodu
    (`FindCodeTextTool`). Każda dokłada wyłącznie `find()`, więc tekst dla modelu jest ten sam
    w testach i na produkcji.

    Flow:
        1. `run()` woła `find()` podklasy i dostaje `FindCodeTextResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "find_code_text"
    description = read_description(__file__)
    args_model  = FindCodeTextQuery

    @abstractmethod
    async def find(
        self,
        query: FindCodeTextQuery,  # np. FindCodeTextQuery(exact="Brak sekwencji numeracji")
    ) -> FindCodeTextResult:
        """
        Description:
        Znajduje linie kodu aplikacji, w których stoi fraza albo wszystkie słowa z zapytania:
        trafienia frazą najpierw, przycięte limitem.

        Example args:
            query=FindCodeTextQuery(exact="Brak sekwencji numeracji")

        Example result:
            FindCodeTextResult(lines=[MatchedLine(path="src/lib/…/GeneratorNumeru.php", line=9,
                                                  matched_by="exact", text="throw new …")],
                               omitted_over_limit=0)
        """

    async def run(
        self,
        args: FindCodeTextQuery,  # np. FindCodeTextQuery(words="sekwencji numeracji")
    ) -> str:
        """
        Description:
        Szuka i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=FindCodeTextQuery(exact="Brak sekwencji numeracji")

        Example result:
            {"lines": [{"path": "src/lib/…/GeneratorNumeru.php", "line": 9, "matched_by": "exact",
                        "text": "throw new …"}], "omitted_over_limit": 0}
        """
        result = await self.find(args)
        text   = result_as_json(result)

        return text
