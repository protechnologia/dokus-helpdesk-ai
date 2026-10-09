"""
Description:
To, co wspólne dla prawdziwego `quote_code` i jego atrapy: nazwa, materiał, klasa zapytania,
potwierdzenie cytowania i lista źródeł (`cite()`). Narzędzie i atrapa różnią się wyłącznie tym,
skąd wiedzą, że plik istnieje i ile ma linii (`search()`).

Przed — wynik cytowania:

    QuoteCodeResult(
        path      = "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
        from_line = 8,
        to_line   = 10,
        role      = "cause",
    )

Po — tekst dla modelu, bez treści linii:

    {
      "path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
      "from_line": 8,
      "to_line": 10,
      "role": "cause"
    }

Po — źródło odpowiedzi:

    SourceRef(source="code", item_id="src/lib/Urzad/Numeracja/GeneratorNumeru.php:8-10",
              title="src/lib/Urzad/Numeracja/GeneratorNumeru.php, linie 8–10")

Co decyduje rola:

| rola       | co model dostaje | czy trafia na listę źródeł |
|------------|------------------|----------------------------|
| `cause`    | potwierdzenie    | tak                        |
| `excluded` | potwierdzenie    | nie                        |

O czym pamiętać przy zmianach:

- To JEDYNE narzędzie kodu, które cytuje. Odczyt pliku źródeł nie tworzy: model przechodzi
  przez kilkanaście plików na sprawę, a rozstrzyga jeden do trzech.
- Źródłem jest fragment, nie plik: `item_id` niesie ścieżkę i zakres linii, więc dwa fragmenty
  jednego pliku to dwa źródła, a ten sam fragment zacytowany dwa razy stoi na liście raz.
- Wykluczenie nie cofa źródła: fragment zacytowany jako przyczyna zostaje na liście, także gdy
  model zacytuje go potem jako wykluczony.
- Tytuł to pełna ścieżka, nie sama nazwa pliku: w aplikacji na Symfony dziesiątki kontrolerów
  nazywają się `actions.class.php`.
- Źródło nie ma daty. Wersję kodu wyznacza gałąź, z której zbudowano paczkę; zapisuje ją
  metryczka paczki (`manifest.json`), a narzędzia jej nie czytają (CLAUDE.md -> p. 65).
"""

from app.agent_tools.base import KnowledgeSource, read_description
from app.agent_tools.code.quote_code.errors import LinesOutOfFileError
from app.agent_tools.code.quote_code.models import QuoteCodeQuery, QuoteCodeResult
from app.agent_tools.models import SourceRef


def check_lines_and_build_result(
    query:      QuoteCodeQuery,  # np. QuoteCodeQuery(path="…", from_line=8, to_line=10, …)
    path:       str,             # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php" — z paczki
    line_count: int,             # np. 27 — tyle linii ma plik
) -> QuoteCodeResult:
    """
    Description:
    Sprawdza, czy cytowane linie mieszczą się w pliku, i składa wynik narzędzia: potwierdzenie
    cytowania. Wspólne dla atrapy i narzędzia właściwego: oba najpierw ustalają ścieżkę w paczce
    i długość pliku.

    Sprawdza tylko koniec fragmentu wobec długości pliku. Ścieżkę sprawdził wcześniej czytnik
    paczki, a kolejność linii i długość fragmentu model zapytania.

    Example args:
        query=QuoteCodeQuery(path="src/lib/Urzad/Numeracja/../Numeracja/GeneratorNumeru.php",
                             from_line=8, to_line=10, role="cause")
        path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        line_count=27

    Example result:
        QuoteCodeResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", from_line=8,
                        to_line=10, role="cause")

    Raises:
        LinesOutOfFileError: fragment kończy się za ostatnią linią pliku
    """
    if query.to_line > line_count:
        raise LinesOutOfFileError(path, query.to_line, line_count)

    quote = QuoteCodeResult(
        path      = path,
        from_line = query.from_line,
        to_line   = query.to_line,
        role      = query.role,
    )

    return quote


class QuoteCodeToolBase(KnowledgeSource):
    """
    Description:
    Wspólna część `quote_code`: wszystko poza sprawdzeniem pliku.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeQuoteCodeTool`) i narzędzie właściwe na paczce kodu
    (`QuoteCodeTool`). Każda dokłada wyłącznie `search()`, więc tekst dla modelu i lista źródeł są
    te same w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `QuoteCodeResult` albo zgłasza `UnknownCodeFileError` lub
           `LinesOutOfFileError`.
        2. `render_for_model()` z kontraktu robi z niego JSON — samo potwierdzenie.
        3. `cite()` robi z niego źródło, ale tylko przy roli `cause`.
    """

    name        = "quote_code"
    description = read_description(__file__)
    source      = "code"
    query_model = QuoteCodeQuery

    def cite(
        self,
        result: QuoteCodeResult,  # np. QuoteCodeResult(path="…", from_line=8, to_line=10, …)
    ) -> list[SourceRef]:
        """
        Description:
        Zamienia wynik narzędzia na listę źródeł odpowiedzi. Dostaje ten sam obiekt, z którego
        `render_for_model()` robi tekst dla modelu, i oddaje to, co z tego cytowania trafi na
        listę źródeł, którą człowiek dostaje razem z odpowiedzią:

            rola `cause`     →  jeden wpis: fragment jest źródłem odpowiedzi
            rola `excluded`  →  pusta lista: miejsce sprawdzone i wykluczone źródłem nie jest

        Woła ją węzeł `run_tools` po każdym wykonanym cytowaniu; samo narzędzie jej nie woła.
        Identyfikatorem wpisu jest ścieżka z zakresem linii, a tytułem ta sama ścieżka z zakresem
        zapisanym słowami.

        Example args:
            result=QuoteCodeResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                                   from_line=8, to_line=10, role="cause")

        Example result:
            [SourceRef(source="code", item_id="src/lib/Urzad/Numeracja/GeneratorNumeru.php:8-10",
                       title="src/lib/Urzad/Numeracja/GeneratorNumeru.php, linie 8–10")]
        """
        # --- wykluczenie: zostaje w rozmowie, źródłem odpowiedzi nie jest ---
        if result.role != "cause":
            return []

        one_line = result.from_line == result.to_line
        lines    = (
            f"linia {result.from_line}" if one_line
            else f"linie {result.from_line}–{result.to_line}"
        )

        ref = SourceRef(
            source  = self.source,
            item_id = f"{result.path}:{result.from_line}-{result.to_line}",
            title   = f"{result.path}, {lines}",
        )

        return [ref]
