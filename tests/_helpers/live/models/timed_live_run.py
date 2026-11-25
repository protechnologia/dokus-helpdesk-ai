import dataclasses

from pydantic import BaseModel


@dataclasses.dataclass(frozen=True)
class TimedLiveRun:
    """Wynik jednej sprawy z `run_timed_live_cases()`: stan końcowy grafu i czas sprawy."""

    final:   BaseModel | None  # stan końcowy; None — węzeł `respond` nie przyjął odpowiedzi
    seconds: float             # ile trwała sprawa, od startu, bez czekania na wolne miejsce
