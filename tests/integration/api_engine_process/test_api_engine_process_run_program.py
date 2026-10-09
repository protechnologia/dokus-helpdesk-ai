"""
Description:
Testy integracyjne `run_program()` na prawdziwych procesach: małych programach, które ma każdy
Linux (`echo`, `sh`, `pwd`, `sleep`). Bez stacku i bez ripgrepa.

| sytuacja                                   | oczekiwanie                             |
|--------------------------------------------|-----------------------------------------|
| program kończy pracę                       | kod wyjścia i oba strumienie jako tekst |
| program kończy kodem innym niż zero        | wynik, nie wyjątek                      |
| argument wygląda jak polecenie powłoki     | trafia do programu jako zwykły tekst    |
| programu albo katalogu roboczego nie ma    | `ProcessConfigError`                    |
| program nie kończy w czasie                | `ProcessError`, proces zabity           |
"""

import time
from pathlib import Path

import pytest

from app.engine_process import ProcessConfigError, ProcessError, run_program

# Limit czasu z zapasem: te programy kończą w milisekundach.
TIMEOUT = 5.0


async def test_the_output_and_the_exit_code_come_back(tmp_path: Path) -> None:
    """Sprawdza, czy po programie, który kończy pracę, wracają jego kod wyjścia i to, co wypisał
    na oba strumienie, każdy osobno.

    Wyłapuje wynik, w którym strumień błędów miesza się z wyjściem albo ginie: klient programu
    czyta trafienia z jednego, a przyczynę błędu z drugiego."""
    output = await run_program("sh", ["-c", "echo wynik; echo powód >&2"], tmp_path, TIMEOUT)

    assert output.returncode == 0
    assert output.stdout     == "wynik\n"
    assert output.stderr     == "powód\n"


async def test_a_failing_exit_code_is_a_result_not_an_exception(tmp_path: Path) -> None:
    """Sprawdza, czy program zakończony kodem 3 daje zwykły wynik z tym kodem, a nie wyjątek.

    Wyłapuje uruchamianie, które samo ocenia kod wyjścia: u ripgrepa kod 1 znaczy „nic nie
    znaleziono", więc każde szukanie bez trafień kończyłoby się błędem."""
    output = await run_program("sh", ["-c", "exit 3"], tmp_path, TIMEOUT)

    assert output.returncode == 3


async def test_an_argument_is_text_never_a_shell_command(tmp_path: Path) -> None:
    """Sprawdza, czy argument ze średnikiem, podstawieniem polecenia i przekierowaniem trafia do
    programu znak w znak, a w katalogu roboczym nie powstaje plik, który takie polecenie
    utworzyłoby w powłoce.

    Wyłapuje uruchamianie przez powłokę: tekst, którego szuka model, pochodzi ze zgłoszenia, więc
    wklejone w nim polecenie wykonałoby się w kontenerze."""
    argument = "a; touch wstrzykniete $(touch podstawione) > przekierowane"

    output = await run_program("echo", [argument], tmp_path, TIMEOUT)

    assert output.stdout == f"{argument}\n"
    assert list(tmp_path.iterdir()) == []


async def test_the_program_runs_in_the_given_directory(tmp_path: Path) -> None:
    """Sprawdza, czy program pracuje w katalogu podanym przy wywołaniu: `pwd` wypisuje właśnie
    ten katalog.

    Wyłapuje uruchamianie w katalogu, z którego ruszyła usługa: szukanie obejmowałoby wtedy kod
    samej usługi zamiast paczki, a ścieżki w wyniku liczyłyby się od złego miejsca."""
    output = await run_program("pwd", [], tmp_path, TIMEOUT)

    assert output.stdout.strip() == str(tmp_path.resolve())


async def test_bytes_that_are_not_utf8_do_not_break_the_output(tmp_path: Path) -> None:
    """Sprawdza, czy bajt, który nie jest poprawnym UTF-8, wraca jako znak zastępczy, a tekst
    wokół niego zostaje.

    Wyłapuje dekodowanie, które na jednym złym bajcie kończy się wyjątkiem: jeden plik w innym
    kodowaniu przerywałby każde szukanie, które w niego trafi."""
    output = await run_program("sh", ["-c", "printf 'przed \\377 po'"], tmp_path, TIMEOUT)

    assert output.stdout == "przed � po"


async def test_a_missing_program_is_a_configuration_error(tmp_path: Path) -> None:
    """Sprawdza, czy uruchomienie programu, którego nie ma w systemie, kończy się wyjątkiem
    `ProcessConfigError` z nazwą programu w komunikacie.

    Wyłapuje brak programu zgłoszony jak chwilowa awaria: trasa oddawałaby wtedy 503 „spróbuj
    później" przy obrazie zbudowanym bez programu, czyli przy usterce, której czekanie nie
    naprawi."""
    with pytest.raises(ProcessConfigError, match="nie-ma-takiego-programu"):
        await run_program("nie-ma-takiego-programu", [], tmp_path, TIMEOUT)


async def test_a_missing_working_directory_is_a_configuration_error(tmp_path: Path) -> None:
    """Sprawdza, czy uruchomienie programu w katalogu, którego nie ma, kończy się wyjątkiem
    `ProcessConfigError`, a nie gołym błędem systemu.

    Wyłapuje brak katalogu zgłoszony jako brak programu albo nieobsłużony wyjątek: komunikat
    wskazywałby wtedy na instalację programu, choć zawiniła ścieżka."""
    with pytest.raises(ProcessConfigError, match="pwd"):
        await run_program("pwd", [], tmp_path / "nie-ma", TIMEOUT)


async def test_a_program_over_the_time_limit_is_stopped(tmp_path: Path) -> None:
    """Sprawdza, czy program, który ma pracować 5 sekund, przy limicie 0,2 sekundy kończy się
    wyjątkiem `ProcessError` niebędącym błędem konfiguracji, i czy wraca on po ułamku sekundy,
    a nie po 5 sekundach.

    Wyłapuje uruchamianie bez limitu czasu albo takie, które po limicie czeka na program do
    końca: jedno szukanie na wolnym dysku wstrzymywałoby żądanie użytkownika bez końca."""
    started = time.perf_counter()

    with pytest.raises(ProcessError) as caught:
        await run_program("sleep", ["5"], tmp_path, timeout=0.2)

    assert not isinstance(caught.value, ProcessConfigError)
    assert time.perf_counter() - started < 2.0
