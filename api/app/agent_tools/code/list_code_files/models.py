from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Najwyżej tyle pozycji oddaje jeden spis. W paczce kodu Dokusa mieści się w tym sam katalog
# w 2368 przypadkach z 2375; nie mieści się siedem katalogów z setkami plików. Przy 100
# odpadałyby jeszcze cztery, w tym trzy listy podkatalogów (114–155), czyli spisy modułów.
MAX_ENTRIES_PER_LISTING = 200

# Głębokość spisu, gdy agent jej nie poda. Przy 1 typowy spis oddaje dwie pozycje, a katalog
# główny jedną; przy 2 połowa katalogów daje do 3 pozycji, 90% do 16, a 99% do 127.
DEFAULT_DEPTH = 2

# Czym jest pozycja spisu: katalogiem albo plikiem.
EntryKind = Literal["dir", "file"]


class ListCodeFilesQuery(BaseModel):
    """
    Description:
    O co agent prosi `list_code_files`: katalog z kodu aplikacji i liczbę poziomów, które spis
    ma pokazać. Oba argumenty są opcjonalne: bez ścieżki spis zaczyna się w katalogu głównym
    kodu, bez głębokości pokazuje `DEFAULT_DEPTH` poziomów.

    Głębokość, która nie mieści się w `MAX_ENTRIES_PER_LISTING` pozycjach, nie jest błędem —
    narzędzie oddaje mniej poziomów i mówi o tym w wyniku.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    # Katalog w kodzie aplikacji; brak znaczy katalog główny kodu.
    path:  str | None = Field(default=None, min_length=1, examples=["src/lib/Urzad/Wysylka"])
    # 1 to sam katalog, 2 to także zawartość jego podkatalogów, i tak dalej.
    depth: int        = Field(default=DEFAULT_DEPTH, ge=1, examples=[2])


class CodeDirInfo(BaseModel):
    """
    Description:
    Co `list_code_files` mówi o całym katalogu, niezależnie od tego, ile poziomów oddało: ile
    poziomów ma wszystko, co pod nim leży. Po tej liczbie model widzi, o jaką głębokość poprosić,
    żeby zobaczyć resztę.
    """

    model_config = ConfigDict(extra="forbid")

    # Liczona po najgłębszej gałęzi; zero znaczy, że pod katalogiem nie ma żadnego pliku.
    total_depth: int = Field(ge=0, examples=[3])


class RequestedDepth(BaseModel):
    """
    Description:
    Głębokość, o którą agent prosił `list_code_files` — powtórzona w wyniku, żeby stała obok
    głębokości oddanej (`ReturnedDepth`). Gdy agent jej nie podał, stoi tu wartość domyślna.
    """

    model_config = ConfigDict(extra="forbid")

    depth: int = Field(ge=1, examples=[3])


class ReturnedDepth(BaseModel):
    """
    Description:
    Głębokość, którą `list_code_files` naprawdę oddało, i trzy rzeczy, których agent nie widzi
    w samej liście pozycji: czy limit zmniejszył głębokość, czy katalog sięga głębiej i ile
    pozycji pokazanego poziomu nie weszło do wyniku.

    Limit pozycji działa na dwa sposoby i każdy ma swój sygnał. Zwykle zmniejsza głębokość
    (`depth_cut_by_limit`), a pokazane poziomy są wtedy pełne. Gdy sam katalog ma więcej
    pozycji, niż mieści wynik, głębokości nie da się już zmniejszyć, więc lista jest ucięta,
    a resztę liczy `omitted_over_limit`.
    """

    model_config = ConfigDict(extra="forbid")

    # Zero tylko wtedy, gdy pod katalogiem nie ma żadnego pliku.
    depth:              int  = Field(ge=0, examples=[2])
    # Żądana głębokość nie zmieściła się w limicie pozycji, więc poziomów jest mniej.
    depth_cut_by_limit: bool = Field(examples=[True])
    # Katalog ma więcej poziomów, niż pokazuje wynik: głębiej leżą pozycje, których tu nie ma.
    has_more_depth:     bool = Field(examples=[True])
    # Większe od zera tylko wtedy, gdy sam katalog ma więcej pozycji, niż mieści wynik.
    omitted_over_limit: int  = Field(ge=0, examples=[0])


class CodeDirEntry(BaseModel):
    """
    Description:
    Jedna pozycja spisu `list_code_files`: ścieżka i to, czy jest katalogiem, czy plikiem.
    Ścieżka jest pełna, względna wobec kodu aplikacji — w kształcie, w jakim model poda ją
    odczytowi pliku, szukaniu albo kolejnemu spisowi, bez sklejania z nazwą katalogu.
    """

    model_config = ConfigDict(extra="forbid")

    path: str       = Field(min_length=1, examples=["src/lib/Urzad/Wysylka/LimitZalacznika.php"])
    kind: EntryKind = Field(examples=["file"])


class ListCodeFilesResult(BaseModel):
    """
    Description:
    Co daje jeden spis `list_code_files`: ścieżka katalogu, głębokość wszystkiego, co pod nim
    leży, głębokość żądana, głębokość oddana z jej sygnałami i pozycje. Ścieżka katalogu wraca
    w jednej postaci — względna wobec kodu aplikacji, bez `..`; katalog główny to `.`.

    Głębokości są dwie, bo zwykle się zgadzają, ale nie zawsze: prośbę o trzy poziomy katalogu,
    który ma dwa, kończy sam katalog, a prośbę o trzy poziomy dużego katalogu zmniejsza limit
    pozycji.
    """

    model_config = ConfigDict(extra="forbid")

    path:      str                = Field(min_length=1, examples=["src/lib/Urzad/Wysylka"])
    dir_info:  CodeDirInfo
    requested: RequestedDepth
    returned:  ReturnedDepth
    # W kolejności drzewa: katalog, pod nim jego zawartość; w katalogu podkatalogi przed plikami.
    entries:   list[CodeDirEntry] = Field(default_factory=list)
