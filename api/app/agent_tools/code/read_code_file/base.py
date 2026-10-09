"""
Description:
To, co wspólne dla prawdziwego `read_code_file` i jego atrapy: nazwa, klasa argumentów, wybranie
linii z pliku i tekst dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą linie
pliku (`read()`).

Przed — zapytanie agenta i plik na 14 linii:

    ReadCodeFileQuery(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", from_line=12, to_line=40)

Po — tekst dla modelu:

    {
      "path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
      "file_info": {
        "total_lines": 14
      },
      "requested": {
        "from_line": 12,
        "to_line": 40
      },
      "returned": {
        "from_line": 12,
        "to_line": 14,
        "cut_by_limit": false,
        "end_of_file": true
      },
      "lines": [
        {
          "line": 12,
          "text": "        return $sekwencja->nastepny . '/' . $rok;"
        },
        {
          "line": 13,
          "text": "    }"
        },
        {
          "line": 14,
          "text": "}"
        }
      ]
    }

Co mówi para flag w `returned`:

| `cut_by_limit` | `end_of_file` | co się stało                         | co dalej                |
|----------------|---------------|--------------------------------------|-------------------------|
| `false`        | `false`       | agent dostał dokładnie żądany zakres | plik ma dalsze linie    |
| `true`         | `false`       | limit urwał żądany zakres            | czytać od `to_line` + 1 |
| `false`        | `true`        | zakres kończy się na końcu pliku     | dalej nic nie ma        |

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: niczego nie cytuje i nie ma `cite()`. Model przechodzi przez wiele
  więcej plików, niż potrzebuje do odpowiedzi, więc źródłem jest dopiero fragment zacytowany
  jako przyczyna narzędziem `quote_code`.
- Zakres i obie flagi liczy jedna funkcja, `select_lines_and_build_result()`, wspólna dla
  narzędzia i atrapy: flagi są wyprowadzone z liczb, więc nie mogą im przeczyć.
- „Urwane limitem" znaczy, że zabrakło linii, o które agent prosił. Prośba o równo
  `MAX_LINES_PER_READ` linii limit osiąga, ale niczego nie urywa.
- Koniec zakresu za końcem pliku to nie błąd: agent nie zna długości pliku przed pierwszym
  odczytem. Błędem jest dopiero początek za końcem pliku.
- Treść linii wraca znak w znak, z wcięciem, i nie jest ucinana — inaczej niż w wyniku
  `find_code_text`, który pokazuje samo miejsce trafienia.
- Ścieżka i numery linii są te same, które przyjmuje `quote_code`.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod
from collections.abc import Sequence

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.code.read_code_file.errors import StartOutOfFileError
from app.agent_tools.code.read_code_file.models import (
    MAX_LINES_PER_READ,
    CodeFileInfo,
    CodeLine,
    ReadCodeFileQuery,
    ReadCodeFileResult,
    RequestedLines,
    ReturnedLines,
)


def select_lines_and_build_result(
    query: ReadCodeFileQuery,  # np. ReadCodeFileQuery(path="…", from_line=12, to_line=40)
    path:  str,                # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php" — z paczki
    lines: Sequence[str],      # np. ["<?php", "", "class GeneratorNumeru", …] — cały plik
) -> ReadCodeFileResult:
    """
    Description:
    Wybiera z linii pliku zakres, o który prosi zapytanie, i składa wynik narzędzia: linie
    z numerami, zakres żądany, zakres oddany i dwie flagi mówiące, czy odczyt urwał limit, czy
    skończył się plik. Wspólne dla atrapy i narzędzia właściwego: oba najpierw ustalają ścieżkę
    w paczce i linie pliku.

    Oddany zakres kończy się tam, gdzie wypada najwcześniejsza z trzech granic: koniec żądanego
    zakresu, koniec pliku albo `MAX_LINES_PER_READ` linii od początku odczytu.

    Example args:
        query=ReadCodeFileQuery(path="src/lib/Urzad/Numeracja/../Numeracja/GeneratorNumeru.php",
                                from_line=12, to_line=40)
        path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        lines=["<?php", "", "class GeneratorNumeru", …]  # 14 linii

    Example result:
        ReadCodeFileResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                           file_info=CodeFileInfo(total_lines=14),
                           requested=RequestedLines(from_line=12, to_line=40),
                           returned=ReturnedLines(from_line=12, to_line=14, cut_by_limit=False,
                                                  end_of_file=True),
                           lines=[CodeLine(line=12, text="        return $sekwencja->…"), …])

    Raises:
        StartOutOfFileError: odczyt zaczyna się za ostatnią linią pliku albo plik jest pusty
    """
    total = len(lines)

    # --- początek za końcem pliku (także plik pusty): nie ma ani jednej linii do oddania ---
    if query.from_line > total:
        raise StartOutOfFileError(path, query.from_line, total)

    # --- gdzie odczyt się kończy: żądany koniec w granicach pliku, a potem limit linii ---
    wanted_end = total if query.to_line is None else min(query.to_line, total)
    limit_end  = query.from_line + MAX_LINES_PER_READ - 1
    last       = min(wanted_end, limit_end)

    result = ReadCodeFileResult(
        path      = path,
        file_info = CodeFileInfo(total_lines=total),
        requested = RequestedLines(from_line=query.from_line, to_line=query.to_line),
        returned  = ReturnedLines(
            from_line    = query.from_line,
            to_line      = last,
            cut_by_limit = last < wanted_end,  # zabrakło linii, o które agent prosił
            end_of_file  = last == total,      # ostatnia oddana linia jest ostatnią w pliku
        ),
        lines     = [
            CodeLine(line=number, text=text)
            for number, text in enumerate(lines[query.from_line - 1:last], start=query.from_line)
        ],
    )

    return result


class ReadCodeFileToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `read_code_file`: wszystko poza pobraniem linii pliku.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeReadCodeFileTool`) i narzędzie właściwe na paczce kodu
    (`ReadCodeFileTool`). Każda dokłada wyłącznie `read()`, więc tekst dla modelu jest ten sam
    w testach i na produkcji.

    Flow:
        1. `run()` woła `read()` podklasy i dostaje `ReadCodeFileResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "read_code_file"
    description = read_description(__file__)
    args_model  = ReadCodeFileQuery

    @abstractmethod
    async def read(
        self,
        query: ReadCodeFileQuery,  # np. ReadCodeFileQuery(path="…", from_line=12, to_line=40)
    ) -> ReadCodeFileResult:
        """
        Description:
        Odczytuje z pliku kodu aplikacji zakres linii, o który prosi zapytanie, najwyżej
        `MAX_LINES_PER_READ` linii.

        Example args:
            query=ReadCodeFileQuery(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                                    from_line=12, to_line=40)

        Example result:
            ReadCodeFileResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                               file_info=CodeFileInfo(total_lines=14),
                               requested=RequestedLines(from_line=12, to_line=40),
                               returned=ReturnedLines(from_line=12, to_line=14, …),
                               lines=[CodeLine(line=12, text="        return …"), …])
        """

    async def run(
        self,
        args: ReadCodeFileQuery,  # np. ReadCodeFileQuery(path="src/web/js/_global/bledy.js")
    ) -> str:
        """
        Description:
        Odczytuje plik i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=ReadCodeFileQuery(path="src/web/js/_global/bledy.js")

        Example result:
            {"path": "src/web/js/_global/bledy.js", "file_info": {"total_lines": 8},
             "requested": {"from_line": 1, "to_line": null},
             "returned": {"from_line": 1, "to_line": 8, "cut_by_limit": false,
                          "end_of_file": true},
             "lines": [{"line": 1, "text": "$(document).ajaxError(function (…) {"}, …]}
        """
        result = await self.read(args)
        text   = result_as_json(result)

        return text
