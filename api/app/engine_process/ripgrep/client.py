"""
Description:
Klient programu ripgrep: szuka w katalogu linii, w których stoi podany tekst. Na nim stoi
narzędzie agenta `find_code_text`, które szuka w paczce kodu aplikacji.

Przed — tekst do znalezienia i katalog:

    ripgrep = RipgrepClient(timeout=10.0)

    await ripgrep.find_substring(Path("/code/data/unsafe/code/repo"), "Brak sekwencji numeracji")
    await ripgrep.find_words(Path("/code/data/unsafe/code/repo"), "numeracji sekwencji")

Po — linie, w których ten tekst stoi, po ścieżce i numerze linii:

    [FoundLine(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", line=18,
               text="            throw new BrakSekwencjiException('Brak sekwencji numeracji…")]

Dwie drogi szukania:

| metoda             | co znajduje                                                     |
|--------------------|-----------------------------------------------------------------|
| `find_substring()` | linie z całą frazą, w podanej kolejności                        |
| `find_words()`     | linie ze wszystkimi słowami, w dowolnej kolejności, bez odmiany |

Obie nie rozróżniają wielkości liter i szukają dosłownie: tekst nie jest wyrażeniem regularnym.

Co się dzieje po drodze:

1. Ripgrep rusza w podanym katalogu, z frazą po `-e` i ścieżką po `--` (`run_program()`).
   Przy słowach szuka jednego, najdłuższego, a komplet sprawdza `contains_all()` z `core_util`
   na treści linii.
2. Kod wyjścia 1 to brak trafień; każdy inny niż 0 to `ProcessError`.
3. Wyjście zamienia się na linie (`parse_ripgrep_output()`), ułożone po ścieżce i numerze.

O czym pamiętać przy zmianach:

- Szukanie oddaje WSZYSTKIE pasujące linie. Ile z nich pokazać i ile policzyć jako pominięte,
  rozstrzyga wołający, jak przy tabelach w Postgresie.
- Ripgrep oddaje pliki w kolejności, która zmienia się między przebiegami, więc wynik jest
  układany tutaj. Bez tego limit wołającego ucinałby za każdym razem inne linie.
- Klient nie sprawdza, dokąd prowadzi `inside`: dostaje ścieżkę sprawdzoną przez wołającego
  (`CodePackage.locate()`), względną wobec katalogu.
- Słowa to ciągi znaków, bez odmiany: „limit" znajdzie „limitu", ale nie odwrotnie.
- Pierwsze słowo sprawdza ripgrep, pozostałe `contains_all()`, więc oba muszą tak samo traktować
  wielkość liter. Pilnuje tego `IGNORE_CASE`: flaga ripgrepa i argument funkcji biorą się z niej.
- Kolejne słowa sprawdza się na samej treści linii, nie na wyjściu ripgrepa: tam przed treścią
  stoi ścieżka, więc słowo „js" pasowałoby do każdej linii pliku `.js`.
- Numer linii liczy się jak w `split_lines()` czytnika paczki: linie dzieli tylko `\\n`.
"""

import asyncio
from pathlib import Path

from app.core_util.text import contains_all
from app.engine_process.base import run_program
from app.engine_process.errors import ProcessError
from app.engine_process.ripgrep.models import FoundLine

# Nazwa programu. W obrazie `api` instaluje go Dockerfile; testy na hoście potrzebują go
# w systemie (`apt install ripgrep`).
RIPGREP = "rg"

# Szukanie nie rozróżnia wielkości liter: komunikat z ekranu bywa przepisany inaczej, niż stoi
# w kodzie. Jedna stała dla ripgrepa i dla sprawdzania słów po naszej stronie.
IGNORE_CASE = True

# Argumenty każdego szukania. Po nich idą: flaga wielkości liter, `-e`, szukany tekst, `--`
# i ścieżka.
RIPGREP_ARGUMENTS = (
    "--fixed-strings",  # tekst od modelu to tekst, nie wyrażenie regularne
    "--line-number",    # numer linii, liczony od 1
    "--with-filename",  # ścieżka także wtedy, gdy szukamy w jednym pliku
    "--no-heading",     # każda linia wyjścia niesie własną ścieżkę
    "--null",           # po ścieżce znak zerowy: dwukropek w nazwie pliku niczego nie psuje
    "--color=never",    # bez kodów sterujących w wyjściu
    "--text",           # plik ze znakiem zerowym jest przeszukiwany jak każdy inny
    "--no-ignore",      # wynik nie zależy od plików `.gitignore` na maszynie
    "--hidden",         # ani od tego, czy nazwa pliku zaczyna się od kropki
    "--no-config",      # ani od konfiguracji ripgrepa w środowisku
)

# Flaga ripgrepa dla każdej wartości `IGNORE_CASE`.
CASE_ARGUMENT = {True: "--ignore-case", False: "--case-sensitive"}

# Tą ścieżką ripgrep przeszukuje cały katalog, w którym go uruchomiono.
WHOLE_DIRECTORY = "."

# Kod wyjścia ripgrepa, gdy nic nie pasuje. To wynik, nie błąd.
NO_MATCHES = 1


def parse_ripgrep_output(
    output: str,  # np. "./src/lib/Blad.php\x0018:    throw new Blad('Brak sekwencji');\n"
) -> list[FoundLine]:
    """
    Description:
    Zamienia wyjście ripgrepa na linie, ułożone po ścieżce i numerze linii. Ripgrep oddaje jedno
    trafienie na linię wyjścia: ścieżkę, znak zerowy, numer linii, dwukropek i treść.

    Początkowe `./` znika ze ścieżki: ripgrep dokleja je, gdy przeszukuje cały katalog,
    a ścieżka ma wyglądać tak samo przy szukaniu w całości i w podkatalogu.

    Example args:
        output="./src/lib/Blad.php\\x0018:    throw new Blad('Brak sekwencji');\\n"

    Example result:
        [FoundLine(path="src/lib/Blad.php", line=18, text="    throw new Blad('Brak sekwencji');")]
    """
    rows: list[tuple[str, int, str]] = []

    for row in output.split("\n"):
        # Ostatni element po podziale jest pusty: wyjście kończy się znakiem końca linii.
        if not row:
            continue

        path, _, rest      = row.partition("\0")
        number, _, content = rest.partition(":")

        rows.append((path.removeprefix("./"), int(number), content))

    # Kolejność plików z ripgrepa zmienia się między przebiegami. Para ścieżka i numer jest
    # jedyna, więc treść do porównania nie wchodzi.
    rows.sort()

    return [FoundLine(path=path, line=number, text=content) for path, number, content in rows]


class RipgrepClient:
    """
    Description:
    Szukanie tekstu w katalogu programem ripgrep, uruchamianym jako osobny proces.

    Do czego:
    Na nim stoi narzędzie agenta `find_code_text`: kod aplikacji leży w folderze, bez bazy,
    a ripgrep przeszukuje 11 tys. plików w ułamku sekundy. „Klient", bo przekracza granicę
    procesu (CLAUDE.md -> „Warstwy kodu"); o paczce kodu nie wie nic — dostaje katalog i oddaje
    linie.

    Flow:
        1. Konstruktor zapamiętuje limit czasu jednego szukania; niczego nie uruchamia.
        2. `find_substring()` szuka całej frazy, `find_words()` wszystkich słów w jednej linii.
        3. Obie idą przez `_search()`: jedno uruchomienie ripgrepa i rozbiór jego wyjścia.
    """

    def __init__(
        self,
        timeout: float,  # np. 10.0 — sekundy na jedno szukanie
    ):
        """
        Description:
        Zapamiętuje limit czasu jednego szukania. Nie sprawdza, czy ripgrep jest w systemie:
        jego brak wychodzi przy pierwszym szukaniu.

        Example args:
            timeout=10.0

        Example result:
            RipgrepClient, którego szukanie trwa najwyżej 10 s
        """
        self._timeout = timeout

    async def find_substring(
        self,
        directory: Path,                   # np. Path("/code/data/unsafe/code/repo")
        text:      str,                    # np. "Nie udało się skomunikować z serwerem"
        inside:    str = WHOLE_DIRECTORY,  # np. "src/web/js" — katalog albo plik w `directory`
    ) -> list[FoundLine]:
        """
        Description:
        Znajduje linie, w których stoi podana fraza: dosłownie, w tej kolejności, bez względu na
        wielkość liter. Fraza musi mieścić się w jednej linii, więc każdy ciąg białych znaków
        w niej — także znak nowej linii z przeklejonego komunikatu — liczy się jako jedna spacja.

        Example args:
            directory=Path("/code/data/unsafe/code/repo")
            text="Nie udało się\\nskomunikować z serwerem"
            inside="src/web/js"

        Example result:
            [FoundLine(path="src/web/js/_global/bledy.js", line=12,
                       text="    pokazBlad('Nie udało się skomunikować z serwerem');")]

        Raises:
            ProcessConfigError: nie ma ripgrepa albo katalogu
            ProcessError: szukanie nie skończyło w czasie albo zakończyło się błędem
        """
        phrase = " ".join(text.split())

        # --- nie ma czego szukać: pusta fraza pasowałaby do każdej linii ---
        if not phrase:
            return []

        return await self._search(directory, phrase, inside)

    async def find_words(
        self,
        directory: Path,                   # np. Path("/code/data/unsafe/code/repo")
        words:     str,                    # np. "skomunikować serwerem" — słowa po spacji
        inside:    str = WHOLE_DIRECTORY,  # np. "src/lib" — katalog albo plik w `directory`
    ) -> list[FoundLine]:
        """
        Description:
        Znajduje linie, które zawierają wszystkie podane słowa, w dowolnej kolejności i bez
        względu na wielkość liter. Słowa oddziela spacja; każde jest szukane jako ciąg znaków,
        bez odmiany.

        Example args:
            directory=Path("/code/data/unsafe/code/repo")
            words="skomunikować serwerem"
            inside="."

        Example result:
            [FoundLine(path="src/lib/Urzad/Http/KlientUslugi.php", line=23,
                       text="        throw new Blad('Z serwerem nie udało się skomunikować');")]

        Raises:
            ProcessConfigError: nie ma ripgrepa albo katalogu
            ProcessError: szukanie nie skończyło w czasie albo zakończyło się błędem
        """
        parts = words.split()

        # --- nie ma czego szukać ---
        if not parts:
            return []

        # Ripgrep szuka jednego słowa, resztę sprawdzamy sami na treści linii. Które słowo
        # dostanie, nie zmienia wyniku, tylko czas: im rzadsze, tym mniej linii do przejrzenia.
        # Najdłuższe to tanie przybliżenie najrzadszego — w sondzie trafne w 3 parach z 5, a przy
        # „function execute" gorsze o 0,3 s.
        anchor  = max(parts, key=len)
        matched = await self._search(directory, anchor, inside)

        kept = [
            line for line in matched
            if contains_all(line.text, parts, ignore_case=IGNORE_CASE)
        ]

        return kept

    async def _search(
        self,
        directory: Path,  # np. Path("/code/data/unsafe/code/repo")
        phrase:    str,   # np. "Brak sekwencji numeracji" — bez znaków nowej linii
        inside:    str,   # np. "src/lib" albo "."
    ) -> list[FoundLine]:
        """
        Description:
        Uruchamia ripgrepa w katalogu i oddaje wszystkie linie z podaną frazą, po ścieżce
        i numerze linii.

        Example args:
            directory=Path("/code/data/unsafe/code/repo")
            phrase="Brak sekwencji numeracji"
            inside="src/lib"

        Example result:
            [FoundLine(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", line=18, text="…")]

        Raises:
            ProcessConfigError: nie ma ripgrepa albo katalogu
            ProcessError: szukanie nie skończyło w czasie albo zakończyło się błędem
        """
        # Fraza po `-e`, ścieżka po `--`: żadna nie zostanie wzięta za flagę programu.
        arguments = [*RIPGREP_ARGUMENTS, CASE_ARGUMENT[IGNORE_CASE], "-e", phrase, "--", inside]
        output    = await run_program(RIPGREP, arguments, directory, self._timeout)

        # --- brak trafień ---
        if output.returncode == NO_MATCHES:
            return []

        # --- ripgrep nie przeszukał katalogu w całości ---
        if output.returncode != 0:
            raise ProcessError(
                f"program `{RIPGREP}` zakończył szukanie błędem (kod {output.returncode}): "
                f"{output.stderr.strip()}"
            )

        # W wątku, nie w pętli zdarzeń: przy zbyt ogólnej frazie wyjście ma kilkanaście megabajtów
        # (85 tys. linii to 0,7 s rozbioru), a w tym czasie inne żądania mają iść dalej.
        return await asyncio.to_thread(parse_ripgrep_output, output.stdout)
