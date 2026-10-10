"""
Description:
To, co wspólne dla prawdziwego `list_code_files` i jego atrapy: nazwa, klasa argumentów,
wybranie pozycji spisu i tekst dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd
biorą ścieżki plików leżących pod katalogiem (`list_dir()`).

Przed — zapytanie agenta i pliki pod katalogiem:

    ListCodeFilesQuery(path="src/lib/Urzad/Wysylka", depth=1)

    ["src/lib/Urzad/Wysylka/Edoreczenia/PobieranieSkrzynki.php",
     "src/lib/Urzad/Wysylka/Epuap/WysylkaEpuap.php",
     "src/lib/Urzad/Wysylka/LimitZalacznika.php"]

Po — tekst dla modelu:

    {
      "path": "src/lib/Urzad/Wysylka",
      "dir_info": {
        "total_depth": 2
      },
      "requested": {
        "depth": 1
      },
      "returned": {
        "depth": 1,
        "depth_cut_by_limit": false,
        "has_more_depth": true,
        "omitted_over_limit": 0
      },
      "entries": [
        {
          "path": "src/lib/Urzad/Wysylka/Edoreczenia",
          "kind": "dir"
        },
        {
          "path": "src/lib/Urzad/Wysylka/Epuap",
          "kind": "dir"
        },
        {
          "path": "src/lib/Urzad/Wysylka/LimitZalacznika.php",
          "kind": "file"
        }
      ]
    }

Co mówią sygnały w `returned`:

| sygnał               | kiedy jest prawdziwy albo większy od zera       | co dalej                |
|----------------------|-------------------------------------------------|-------------------------|
| `depth_cut_by_limit` | żądana głębokość nie zmieściła się w limicie    | spis podkatalogu osobno |
| `has_more_depth`     | katalog ma więcej poziomów, niż pokazuje wynik  | spis głębiej            |
| `omitted_over_limit` | sam katalog ma więcej pozycji, niż mieści wynik | szukanie w tym katalogu |

Gdy wszystkie trzy milczą, wynik pokazuje wszystko, co leży pod katalogiem. Przy uciętej
głębokości pokazane poziomy są pełne; lista bywa niepełna tylko przy `omitted_over_limit`
większym od zera.

Jak powstaje spis:

1. Ze ścieżek plików powstają poziomy: pierwszy to pozycje samego katalogu, drugi to zawartość
   jego podkatalogów, i tak dalej. Katalogiem jest każdy człon ścieżki przed nazwą pliku.
2. Wynik bierze tyle pełnych poziomów, ile mieści `MAX_ENTRIES_PER_LISTING`, najwyżej żądaną
   głębokość.
3. Gdy nie mieści się nawet pierwszy poziom, wynik bierze jego początek: podkatalogi przed
   plikami.
4. Pozycje stoją w kolejności drzewa: katalog, pod nim jego zawartość.

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: niczego nie cytuje i nie ma `cite()`. Spis mówi, co gdzie leży,
  nie co w plikach stoi.
- Głębokość i sygnały liczy jedna funkcja, `select_entries_and_build_result()`, wspólna dla
  narzędzia i atrapy: sygnały są wyprowadzone z liczb, więc nie mogą im przeczyć.
- Limit zmniejsza głębokość, zamiast ucinać listę w środku poziomu. Po uciętym poziomie nie
  byłoby widać, które podkatalogi są rozwinięte, a które tylko wyglądają na puste.
- `omitted_over_limit` liczy wyłącznie pozycje pokazanego poziomu. Pozycji z poziomów, których
  wynik nie pokazuje, nie liczy: o nich mówią `depth_cut_by_limit` i `has_more_depth`.
- Katalogu bez plików w spisie nie ma: katalogi powstają tu ze ścieżek plików, a paczka
  pustych katalogów nie zawiera.
- Ścieżki pozycji są pełne — te same przyjmują `read_code_file`, `find_code_text` (jako `path`)
  i kolejny spis.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod
from collections.abc import Sequence

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.code.list_code_files.models import (
    MAX_ENTRIES_PER_LISTING,
    CodeDirEntry,
    CodeDirInfo,
    EntryKind,
    ListCodeFilesQuery,
    ListCodeFilesResult,
    RequestedDepth,
    ReturnedDepth,
)

# Ścieżka katalogu głównego kodu — w tej postaci oddaje go czytnik paczki.
ROOT_DIR = "."


def _tree_order(
    entry: tuple[str, EntryKind],  # np. ("src/lib/Urzad/Wysylka/LimitZalacznika.php", "file")
) -> list[tuple[bool, str]]:
    """
    Description:
    Klucz sortowania pozycji w kolejności drzewa: katalog stoi tuż przed swoją zawartością,
    a w jednym katalogu podkatalogi stoją przed plikami, jedne i drugie po nazwie. Każdy człon
    ścieżki przed ostatnim jest katalogiem, więc o „plik czy katalog" pyta się tylko ostatni.

    Example args:
        entry=("src/web/index.php", "file")

    Example result:
        [(False, "src"), (False, "web"), (True, "index.php")]
    """
    path, kind = entry
    parts      = path.split("/")
    key        = [(False, part) for part in parts[:-1]] + [(kind == "file", parts[-1])]

    return key


def select_entries_and_build_result(
    query: ListCodeFilesQuery,  # np. ListCodeFilesQuery(path="src/lib/Urzad/Wysylka", depth=1)
    path:  str,                 # np. "src/lib/Urzad/Wysylka" — z paczki; "." to katalog główny
    files: Sequence[str],       # np. ["src/lib/Urzad/Wysylka/LimitZalacznika.php", …] — pod nim
) -> ListCodeFilesResult:
    """
    Description:
    Wybiera ze ścieżek plików leżących pod katalogiem pozycje spisu i składa wynik narzędzia:
    pozycje do żądanej głębokości, głębokość całego katalogu, głębokość oddaną i sygnały
    mówiące, czy limit pozycji coś zabrał. Wspólne dla atrapy i narzędzia właściwego: oba
    najpierw ustalają ścieżkę katalogu w paczce i pliki pod nim.

    Wynik bierze tyle pełnych poziomów, ile mieści `MAX_ENTRIES_PER_LISTING`. Gdy nie mieści się
    nawet pierwszy, bierze jego początek, podkatalogi przed plikami, i liczy resztę.

    Example args:
        query=ListCodeFilesQuery(path="src/lib/Urzad/Wysylka", depth=1)
        path="src/lib/Urzad/Wysylka"
        files=["src/lib/Urzad/Wysylka/Edoreczenia/PobieranieSkrzynki.php",
               "src/lib/Urzad/Wysylka/Epuap/WysylkaEpuap.php",
               "src/lib/Urzad/Wysylka/LimitZalacznika.php"]

    Example result:
        ListCodeFilesResult(path="src/lib/Urzad/Wysylka",
                            dir_info=CodeDirInfo(total_depth=2),
                            requested=RequestedDepth(depth=1),
                            returned=ReturnedDepth(depth=1, depth_cut_by_limit=False,
                                                   has_more_depth=True, omitted_over_limit=0),
                            entries=[CodeDirEntry(path="src/lib/Urzad/Wysylka/Edoreczenia",
                                                  kind="dir"), …])
    """
    # --- poziomy: pozycje samego katalogu, potem zawartość podkatalogów, i tak dalej ---
    prefix = "" if path == ROOT_DIR else f"{path}/"
    levels: dict[int, dict[str, EntryKind]] = {}

    for file in files:
        parts = file.removeprefix(prefix).split("/")

        for level in range(1, len(parts) + 1):
            # Ostatni człon ścieżki to plik, każdy wcześniejszy to katalog.
            kind: EntryKind = "file" if level == len(parts) else "dir"

            levels.setdefault(level, {})[prefix + "/".join(parts[:level])] = kind

    total_depth = max(levels, default=0)
    wanted      = min(query.depth, total_depth)

    # --- tyle pełnych poziomów, ile mieści limit pozycji ---
    shown = 0
    count = 0

    for level in range(1, wanted + 1):
        if count + len(levels[level]) > MAX_ENTRIES_PER_LISTING:
            break

        shown  = level
        count += len(levels[level])

    kept    = [entry for level in range(1, shown + 1) for entry in levels[level].items()]
    omitted = 0

    # --- sam katalog ponad limit: głębokości nie da się zmniejszyć, więc lista jest ucięta ---
    if shown == 0 and wanted >= 1:
        first   = sorted(levels[1].items(), key=_tree_order)
        kept    = first[:MAX_ENTRIES_PER_LISTING]
        omitted = len(first) - len(kept)
        shown   = 1

    result = ListCodeFilesResult(
        path      = path,
        dir_info  = CodeDirInfo(total_depth=total_depth),
        requested = RequestedDepth(depth=query.depth),
        returned  = ReturnedDepth(
            depth              = shown,
            depth_cut_by_limit = shown < wanted,       # agent prosił o poziomy, które są
            has_more_depth     = shown < total_depth,  # głębiej leżą pozycje spoza wyniku
            omitted_over_limit = omitted,
        ),
        entries   = [
            CodeDirEntry(path=entry_path, kind=kind)
            for entry_path, kind in sorted(kept, key=_tree_order)
        ],
    )

    return result


class ListCodeFilesToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `list_code_files`: wszystko poza pobraniem ścieżek plików.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeListCodeFilesTool`) i narzędzie właściwe na paczce
    kodu (`ListCodeFilesTool`). Każda dokłada wyłącznie `list_dir()`, więc tekst dla modelu
    jest ten sam w testach i na produkcji.

    Flow:
        1. `run()` woła `list_dir()` podklasy i dostaje `ListCodeFilesResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "list_code_files"
    description = read_description(__file__)
    args_model  = ListCodeFilesQuery

    @abstractmethod
    async def list_dir(
        self,
        query: ListCodeFilesQuery,  # np. ListCodeFilesQuery(path="src/lib/Urzad/Wysylka")
    ) -> ListCodeFilesResult:
        """
        Description:
        Spisuje katalog z kodu aplikacji do głębokości, o którą prosi zapytanie, najwyżej
        `MAX_ENTRIES_PER_LISTING` pozycji.

        Example args:
            query=ListCodeFilesQuery(path="src/lib/Urzad/Wysylka", depth=1)

        Example result:
            ListCodeFilesResult(path="src/lib/Urzad/Wysylka",
                                dir_info=CodeDirInfo(total_depth=2),
                                requested=RequestedDepth(depth=1),
                                returned=ReturnedDepth(depth=1, depth_cut_by_limit=False, …),
                                entries=[CodeDirEntry(path="src/lib/Urzad/Wysylka/Edoreczenia",
                                                      kind="dir"), …])
        """

    async def run(
        self,
        args: ListCodeFilesQuery,  # np. ListCodeFilesQuery(path="src/web/js")
    ) -> str:
        """
        Description:
        Spisuje katalog i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=ListCodeFilesQuery(path="src/web/js", depth=1)

        Example result:
            {"path": "src/web/js", "dir_info": {"total_depth": 2}, "requested": {"depth": 1},
             "returned": {"depth": 1, "depth_cut_by_limit": false, "has_more_depth": true,
                          "omitted_over_limit": 0},
             "entries": [{"path": "src/web/js/_global", "kind": "dir"}, …]}
        """
        result = await self.list_dir(args)
        text   = result_as_json(result)

        return text
