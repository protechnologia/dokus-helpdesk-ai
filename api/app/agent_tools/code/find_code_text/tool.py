"""
Description:
Prawdziwe narzędzie `find_code_text`: znajduje w paczce kodu aplikacji linie, w których stoi
podany tekst, i oddaje je ze ścieżką, numerem i treścią. Nie woła embeddera, bazy ani LLM-a —
tylko program ripgrep na folderze paczki.

    `exact` → cała fraza w linii ───────────┐
                                            ├→ jedna lista, każda linia raz → limit → linie
    `words` → wszystkie słowa w linii ──────┘

Przed — zapytanie agenta:

    FindCodeTextQuery(exact="Nie udało się skomunikować z serwerem", words="skomunikować serwerem")

Po — wynik `find()` (frazę mają dwie linie, oba słowa — te same i jeszcze jedna o innym szyku):

    FindCodeTextResult(
        lines = [
            MatchedLine(path="src/web/js/_global/bledy.js", line=12, matched_by="exact",
                        text="APP.zdarzenia.wywolaj('okna/pokazBlad', { tresc: 'Nie udało…"),
            MatchedLine(path="src/web/js/archiwum/archiwum.js", line=9, matched_by="exact",
                        text="APP.zdarzenia.wywolaj('okna/pokazBlad', { tresc: 'Nie udało…"),
            MatchedLine(path="src/lib/Urzad/Http/KlientUslugi.php", line=23, matched_by="words",
                        text="throw new \\RuntimeException('Z serwerem usługi nie udało się…"),
        ],
        omitted_over_limit = 0,
    )

Co się dzieje po drodze:

1. Czytnik paczki sprawdza ścieżkę zawężenia; ścieżka spoza paczki albo donikąd kończy się
   `UnknownCodePathError`.
2. Ripgrep szuka frazy z `exact` i słów z `words`, każdego osobno, bez względu na wielkość
   liter.
3. Wyniki łączą się w jedną listę: najpierw linie znalezione frazą, potem słowami, każde po
   ścieżce i numerze linii. Linia znaleziona obiema drogami stoi raz, jako znaleziona frazą.
4. Lista jest cięta do `MAX_LINES_PER_SEARCH`; reszta jest policzona w `omitted_over_limit`.
5. Treść każdej pokazanej linii traci wcięcie i jest ucinana po `MAX_TEXT_CHARS` znakach.

O czym pamiętać przy zmianach:

- Pola szukają niezależnie i wyniki się sumują, jak w `find_tickets_text`. Linia nie musi
  pasować do obu.
- Fraza i słowa muszą stać w jednej linii kodu. Komunikat składany w kodzie z części nie
  istnieje w nim w całości, stąd rada w opisie dla modelu: szukać stałego fragmentu.
- Słowa nie mają odmiany. Słownik odmienia w Postgresie; tu szuka ripgrep, po ciągach znaków.
- Kolejność jest alfabetyczna, nie według trafności: gdy pasuje więcej linii, niż mieści wynik,
  model widzi pierwsze pliki, a nie najważniejsze. Stąd `omitted_over_limit` i zawężanie.
- Brak paczki albo ripgrepa to błąd konfiguracji: nie wraca do modelu, zatrzymuje przebieg.
  Inaczej model dostawałby „nic nie znaleziono" na każde pytanie i uznawał, że kod nic nie mówi.
"""

import logging
from itertools import islice

from app.agent_tools.code.find_code_text.base import FindCodeTextToolBase, shorten_line
from app.agent_tools.code.find_code_text.errors import UnknownCodePathError
from app.agent_tools.code.find_code_text.models import (
    MAX_LINES_PER_SEARCH,
    FindCodeTextQuery,
    FindCodeTextResult,
    MatchedLine,
)
from app.agent_tools.models import MatchKind
from app.core_service.loader_code_package import CodePackage, CodePathError
from app.engine_process.ripgrep import WHOLE_DIRECTORY, FoundLine, RipgrepClient

logger = logging.getLogger(__name__)


class FindCodeTextTool(FindCodeTextToolBase):
    """
    Description:
    `find_code_text` na prawdziwej paczce kodu: ripgrep znajduje linie z frazą i ze słowami,
    a narzędzie łączy wyniki, tnie je limitem i oddaje linie z treścią.

    Do czego:
    Szukanie w kodzie aplikacji w grafach `search`, `suggest_questions` i `suggest_solution` —
    od niego zaczyna się sprawa, w której zgłoszenie niesie komunikat z ekranu, wpis z logu albo
    kod błędu, a zgłoszenia i instrukcje nic o nim nie mówią. Tylko do odczytu.

    Flow:
        1. `find()` ustala, gdzie szukać: cały kod albo ścieżka sprawdzona przez czytnik paczki.
        2. Pyta ripgrepa o frazę z `exact` i o słowa z `words`.
        3. Łączy trafienia w jedną listę z etykietami, tnie ją limitem i liczy resztę.
        4. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        package: CodePackage,    # np. CodePackage(Path("/code/data/unsafe/code"))
        ripgrep: RipgrepClient,  # np. RipgrepClient(timeout=10.0)
    ):
        """
        Description:
        Spina narzędzie z paczką kodu i z klientem ripgrepa. Oba są wstrzykiwane, nie budowane
        tutaj: paczka pilnuje ścieżek, klient szuka.

        Example args:
            package=CodePackage(Path("/code/data/unsafe/code"))
            ripgrep=RipgrepClient(timeout=10.0)

        Example result:
            FindCodeTextTool gotowe do szukania w paczce kodu
        """
        self._package = package
        self._ripgrep = ripgrep

    async def find(
        self,
        query: FindCodeTextQuery,  # np. FindCodeTextQuery(exact="Brak sekwencji numeracji")
    ) -> FindCodeTextResult:
        """
        Description:
        Znajduje linie kodu, w których stoi fraza z `exact` albo wszystkie słowa z `words`:
        znalezione frazą najpierw, przycięte limitem.

        Example args:
            query=FindCodeTextQuery(exact="function executeZapisz(", path="src/apps/frontend")

        Example result:
            FindCodeTextResult(lines=[MatchedLine(path="src/apps/frontend/modules/kontrahenci/…",
                                                  line=13, matched_by="exact",
                                                  text="public function executeZapisz(…")],
                               omitted_over_limit=0)

        Raises:
            UnknownCodePathError: `path` nie wskazuje pliku ani katalogu w paczce
            CodePackageConfigError: paczki nie ma pod skonfigurowaną ścieżką
            ProcessConfigError: nie ma programu ripgrep
            ProcessError: szukanie nie skończyło w czasie albo zakończyło się błędem
        """
        # --- gdzie szukać: katalog z kodem, a w nim całość albo sprawdzona ścieżka zawężenia ---
        directory = self._package.repo_dir()
        inside    = WHOLE_DIRECTORY

        if query.path:
            try:
                inside = self._package.locate(query.path, allow_dir=True)
            except CodePathError as exc:
                # `from None`: wyjątek czytnika niczego tu nie dodaje, a komunikat idzie do modelu.
                raise UnknownCodePathError(str(exc)) from None

        # --- fraza i słowa: każde osobno ---
        exact_lines: list[FoundLine] = []
        words_lines: list[FoundLine] = []

        if query.exact:
            exact_lines = await self._ripgrep.find_substring(directory, query.exact, inside)

        if query.words:
            words_lines = await self._ripgrep.find_words(directory, query.words, inside)

        # --- jedna lista: fraza przed słowami, linia znaleziona obiema drogami stoi raz ---
        matched: dict[tuple[str, int], tuple[MatchKind, FoundLine]] = {}

        for line in exact_lines:
            matched.setdefault((line.path, line.line), ("exact", line))

        for line in words_lines:
            matched.setdefault((line.path, line.line), ("words", line))

        # --- cięcie limitem; resztę liczymy, zamiast gubić ---
        kept    = list(islice(matched.values(), MAX_LINES_PER_SEARCH))
        omitted = len(matched) - len(kept)

        # Same liczby: zapytanie agenta niesie treść zgłoszenia, a ścieżka układ kodu klienta.
        logger.info(
            "find_code_text exact=%s words=%s narrowed=%s matched=%d omitted=%d",
            bool(query.exact),
            bool(query.words),
            bool(query.path),
            len(matched),
            omitted,
        )

        result = FindCodeTextResult(
            lines = [
                MatchedLine(
                    path       = line.path,
                    line       = line.line,
                    matched_by = kind,
                    text       = shorten_line(line.text),
                )
                for kind, line in kept
            ],
            omitted_over_limit = omitted,
        )

        return result
