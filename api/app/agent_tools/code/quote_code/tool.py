"""
Description:
Prawdziwe narzędzie `quote_code`: zapisuje fragment pliku z paczki kodu jako cytowanie. Nie woła
embeddera, bazy ani LLM-a — tylko folder paczki, i tylko po to, żeby sprawdzić, że plik i linie
istnieją.

    ścieżka i zakres linii → plik w paczce → długość pliku → potwierdzenie cytowania

Przed — zapytanie agenta:

    QuoteCodeQuery(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                   from_line=17, to_line=19, role="cause")

Po — wynik `search()`:

    QuoteCodeResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                    from_line=17, to_line=19, role="cause")

Co się dzieje po drodze:

1. Czytnik paczki sprawdza ścieżkę i oddaje ją w jednej postaci, względnej wobec kodu.
2. Ścieżka spoza paczki, katalog albo brak pliku kończy się `UnknownCodeFileError`.
3. Fragment, który kończy się za ostatnią linią pliku, kończy się `LinesOutOfFileError`.
4. Wynikiem jest samo potwierdzenie: ścieżka, zakres i rola.

O czym pamiętać przy zmianach:

- Treści linii narzędzie nie oddaje, choć plik czyta. Cytowanie, które pokazuje kod, model
  bierze za odczyt i cytuje linie, których nie przeczytał.
- Czy model czytał cytowane linie, narzędzie nie sprawdza: nie widzi rozmowy. Mówi o tym opis
  dla modelu, a liczy pomiar (CLAUDE.md -> p. 59).
- Długość fragmentu i kolejność linii sprawdza model zapytania, zanim narzędzie ruszy.
- Brak paczki pod skonfigurowaną ścieżką to `CodePackageConfigError`: nie wraca do modelu,
  zatrzymuje przebieg. Inaczej model dostawałby „nie ma takiego pliku" na każde cytowanie.
"""

import logging

from app.agent_tools.code.quote_code.base import QuoteCodeToolBase, check_lines_and_build_result
from app.agent_tools.code.quote_code.errors import UnknownCodeFileError
from app.agent_tools.code.quote_code.models import QuoteCodeQuery, QuoteCodeResult
from app.core_service.loader_code_package import CodePackage, CodePathError

logger = logging.getLogger(__name__)


class QuoteCodeTool(QuoteCodeToolBase):
    """
    Description:
    `quote_code` na prawdziwej paczce kodu: sprawdza, że cytowany fragment istnieje, i oddaje
    potwierdzenie.

    Do czego:
    Jedyne narzędzie kodu, które dokłada do listy źródeł, w grafach `search`,
    `suggest_questions` i `suggest_solution`. Źródłem jest fragment zacytowany jako przyczyna,
    a nie każdy plik, przez który model przeszedł. Tylko do odczytu.

    Flow:
        1. `search()` ustala ścieżkę w paczce i liczy linie pliku.
        2. `check_lines_and_build_result()` sprawdza, że fragment mieści się w pliku, i składa
           potwierdzenie.
        3. `render_for_model()` i `cite()` z klas bazowych robią z wyniku tekst i źródło.
    """

    def __init__(
        self,
        package: CodePackage,  # np. CodePackage(Path("/code/data/unsafe/code"))
    ):
        """
        Description:
        Spina narzędzie z paczką kodu. Paczka jest wstrzykiwana, nie budowana tutaj.

        Example args:
            package=CodePackage(Path("/code/data/unsafe/code"))

        Example result:
            QuoteCodeTool gotowe do cytowania plików z paczki
        """
        self._package = package

    async def search(
        self,
        query: QuoteCodeQuery,  # np. QuoteCodeQuery(path="…", from_line=17, to_line=19, …)
    ) -> QuoteCodeResult:
        """
        Description:
        Sprawdza, że fragment istnieje w paczce, i oddaje potwierdzenie cytowania.

        Example args:
            query=QuoteCodeQuery(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                                 from_line=17, to_line=19, role="cause")

        Example result:
            QuoteCodeResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", from_line=17,
                            to_line=19, role="cause")

        Raises:
            UnknownCodeFileError: ścieżka nie wskazuje pliku w paczce
            LinesOutOfFileError: fragment kończy się za ostatnią linią pliku
            CodePackageConfigError: paczki nie ma pod skonfigurowaną ścieżką
        """
        # --- plik: ścieżka w jednej postaci i liczba linii ---
        try:
            path       = self._package.locate(query.path)
            line_count = len(self._package.read_lines(path))
        except CodePathError as exc:
            # `from None`: wyjątek czytnika niczego tu nie dodaje, a komunikat idzie do modelu.
            raise UnknownCodeFileError(str(exc)) from None

        quote = check_lines_and_build_result(query, path, line_count)

        # Rola i liczby: ścieżkę podaje model, a wskazuje ona miejsce w kodzie klienta.
        logger.info(
            "quote_code role=%s lines=%d",
            quote.role,
            quote.to_line - quote.from_line + 1,
        )

        return quote
