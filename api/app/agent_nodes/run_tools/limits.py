"""
Description:
Limity wywołań narzędzi w jednym przebiegu grafu: które wywołania z ostatniej tury modelu są
ponad limit i co model dostaje zamiast wyniku. Wspólne dla węzła `run_tools` i jego atrapy, żeby
oba liczyły tak samo.

Przed — rozmowa, w której model wołał `find_tickets_vector` już dwa razy, i limit 2:

    messages = [tura("find_tickets_vector"), …, tura("find_tickets_vector"), …,
                tura("find_tickets_vector", call_id="call_5")]
    limits   = {"find_tickets_vector": 2}

Po — identyfikatory wywołań ponad limit:

    {"call_5"}

Co się dzieje po drodze:

1. Wywołania z wcześniejszych tur są policzone z wiadomości w stanie grafu — osobnego licznika
   w stanie nie ma. Liczą się te, które dały wynik; wywołanie, na które model dostał błąd,
   limitu nie zużywa.
2. Wywołania z ostatniej tury idą po kolei: mieszczące się w limicie podbijają licznik, kolejne
   są ponad limit.
3. Wywołanie ponad limit dostaje `limit_exceeded_text()` zamiast wyniku i nie dokłada źródeł.

O czym pamiętać przy zmianach:

- Limit dotyczy jednego przebiegu grafu, czyli jednej sprawy, i liczy WYWOŁANIA, nie pobrane
  elementy. Ile jedno wywołanie może pobrać, ustala model zapytania narzędzia.
- Wywołanie zakończone błędem (złe argumenty, nieznany numer, odmowa z powodu limitu) nie
  zużywa limitu: błąd wraca do modelu po to, żeby mógł wywołanie poprawić, a limit odczytu
  wątków ma być liczbą wątków przeczytanych. Pętlę samych błędów ucina limit tur modelu.
- W obrębie jednej tury miejsca w limicie są rozdzielane przed wykonaniem: wywołanie, które
  potem skończy się błędem, zajmuje swoje do końca tej tury i zwalnia je dopiero w następnej.
- Narzędzie bez wpisu w `limits` nie ma limitu. Mapę z konfiguracji daje
  `Settings.tool_call_limits()`, a w niej jest każde narzędzie.
- Tekst błędu czyta model: mówi, co się stało i co dalej. Żądanie się nie wywala.
"""

from collections import Counter
from collections.abc import Mapping, Sequence

from app.agent_tools.base import error_as_json, is_error_json
from app.engine_llm import ChatMessage


def calls_over_limit(
    messages: Sequence[ChatMessage],  # cała rozmowa; ostatnia wiadomość zleca narzędzia
    limits:   Mapping[str, int],      # np. {"find_tickets_vector": 3, "read_docs": 2}
) -> set[str]:
    """
    Description:
    Wskazuje wywołania z ostatniej tury modelu, które przekraczają limit swojego narzędzia —
    licząc wywołania z wcześniejszych tur, które dały wynik, i te stojące przed nimi w tej samej
    turze.

    Example args:
        messages=[tool_call_turn("read_docs", {…}), …, tool_call_turn("read_docs", {…}, "call_3")]
        limits={"read_docs": 1}

    Example result:
        {"call_3"}
    """
    # --- nie ma czego sprawdzać ---
    if not messages:
        return set()

    *earlier, last = messages

    # --- wywołania z wcześniejszych tur: liczą się te, które dały wynik, nie błąd ---
    failed = {
        message.call_id
        for message in earlier
        if message.role == "tool" and is_error_json(message.content)
    }
    used = Counter(
        call.name
        for message in earlier
        for call in message.tool_calls
        if call.call_id not in failed
    )

    # --- ostatnia tura, po kolei ---
    refused: set[str] = set()

    for call in last.tool_calls:
        limit = limits.get(call.name)

        # Mieści się w limicie (albo narzędzie go nie ma): zostanie wykonane, więc liczy się.
        if limit is None or used[call.name] < limit:
            used[call.name] += 1
            continue

        refused.add(call.call_id)

    return refused


def limit_exceeded_text(
    tool_name: str,  # np. "read_tickets_thread"
    limit:     int,  # np. 2
) -> str:
    """
    Description:
    Tekst, który model dostaje zamiast wyniku narzędzia wywołanego ponad limit — JSON z polem
    `error`, jak każdy błąd wracający do modelu (`error_as_json()`).

    Example args:
        tool_name="read_tickets_thread"
        limit=2

    Example result:
        {"error": "Limit wywołań narzędzia `read_tickets_thread` w tej sprawie (2) jest
                   wyczerpany. Nie wołaj go ponownie — odpowiedz na podstawie tego, co już masz."}
    """
    error = (
        f"Limit wywołań narzędzia `{tool_name}` w tej sprawie ({limit}) jest wyczerpany. "
        f"Nie wołaj go ponownie — odpowiedz na podstawie tego, co już masz."
    )

    return error_as_json(error)
