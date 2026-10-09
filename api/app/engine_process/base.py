"""
Description:
Uruchamia program jako osobny proces i oddaje to, co po nim zostało. Wspólne dla klientów
wszystkich programów z tego pakietu: każdy składa własne argumenty i sam czyta wynik, a tu jest
tylko to, co przy każdym programie wygląda tak samo.

Przed — program, argumenty i katalog roboczy:

    await run_program("rg", ["--fixed-strings", "-e", "Brak sekwencji", "--", "."],
                      directory=Path("/code/data/unsafe/code/repo"), timeout=10.0)

Po — kod wyjścia i oba strumienie:

    ProgramOutput(returncode=0, stdout="./src/lib/Blad.php\\x0018:    throw new Blad(…", stderr="")

Klient konkretnego programu leży w podfolderze obok (`ripgrep/`).

Co się dzieje po drodze:

1. Sprawdza, czy program jest w systemie; brak to `ProcessConfigError`.
2. Uruchamia go bez powłoki, w podanym katalogu, bez wejścia.
3. Czeka na koniec najwyżej `timeout` sekund; po tym czasie zabija proces i zgłasza
   `ProcessError`.
4. Oddaje kod wyjścia i wyjście jako tekst w UTF-8.

O czym pamiętać przy zmianach:

- Bez powłoki, zawsze. Argumenty idą do programu jako osobne napisy, więc tekst od modelu —
  z cudzysłowem, średnikiem albo `$(…)` — jest tylko tekstem.
- Kodu wyjścia ta funkcja nie ocenia: co jest błędem, wie klient programu.
- W logu jest nazwa programu, kod wyjścia i czas, nigdy argumenty: niosą tekst, którego szukał
  model, czyli treść zgłoszenia.
- Całe wyjście programu trafia do pamięci. Program, który może oddać gigabajty, potrzebuje
  własnego limitu po stronie argumentów.
"""

import asyncio
import logging
import shutil
import time
from collections.abc import Sequence
from pathlib import Path

from app.engine_process.errors import ProcessConfigError, ProcessError
from app.engine_process.models import ProgramOutput

logger = logging.getLogger(__name__)


async def run_program(
    program:   str,            # np. "rg"
    arguments: Sequence[str],  # np. ["--fixed-strings", "-e", "Brak sekwencji", "--", "."]
    directory: Path,           # np. Path("/code/data/unsafe/code/repo") — katalog roboczy
    timeout:   float,          # sekundy
) -> ProgramOutput:
    """
    Description:
    Uruchamia program bez powłoki w podanym katalogu, czeka na jego koniec i oddaje kod wyjścia
    razem z wyjściem. Kodu nie ocenia.

    Example args:
        program="rg"
        arguments=["--fixed-strings", "-e", "Brak sekwencji", "--", "."]
        directory=Path("/code/data/unsafe/code/repo")
        timeout=10.0

    Example result:
        ProgramOutput(returncode=0, stdout="./src/lib/Blad.php\\x0018:    throw…\\n", stderr="")

    Raises:
        ProcessConfigError: programu nie ma w systemie albo nie da się go uruchomić w katalogu
        ProcessError: program nie skończył w czasie
    """
    # --- program: sprawdzany osobno, bo brak katalogu roboczego zgłasza się tym samym wyjątkiem ---
    if shutil.which(program) is None:
        raise ProcessConfigError(
            f"nie ma programu `{program}` — zainstaluj go w systemie albo w obrazie usługi"
        )

    started = time.perf_counter()

    # --- uruchomienie: bez powłoki, bez wejścia ---
    try:
        process = await asyncio.create_subprocess_exec(
            program, *arguments,
            cwd    = directory,
            stdin  = asyncio.subprocess.DEVNULL,
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.PIPE,
        )
    except (
        FileNotFoundError,   # katalogu roboczego nie ma
        NotADirectoryError,  # katalog roboczy jest plikiem
        PermissionError,     # programu albo katalogu nie wolno użyć
    ) as exc:
        raise ProcessConfigError(
            f"nie da się uruchomić programu `{program}` w katalogu {directory}: {exc.strerror}"
        ) from None

    # --- wynik: całe wyjście naraz, z limitem czasu ---
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        # Proces zostałby po nas i dalej czytał dysk.
        process.kill()
        await process.wait()

        raise ProcessError(f"program `{program}` nie skończył w {timeout:g} s") from None

    output = ProgramOutput(
        returncode = process.returncode,
        stdout     = stdout.decode("utf-8", errors="replace"),
        stderr     = stderr.decode("utf-8", errors="replace"),
    )

    logger.info(
        "process program=%s returncode=%d seconds=%.3f stdout_chars=%d",
        program,
        output.returncode,
        time.perf_counter() - started,
        len(output.stdout),
    )

    return output
