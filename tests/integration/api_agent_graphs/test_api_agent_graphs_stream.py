import asyncio
import time
from datetime import timedelta
from itertools import pairwise
from types import ModuleType

import pytest

from app.agent_graphs import gate_close, search
from app.agent_graphs.fake import FAKE_READ_ARGUMENTS, FAKE_SEARCH_ARGUMENTS
from app.engine_anonymization import AnonymizedText, FakeAnonymizer
from tests._helpers.graphs import graph_modules, graph_name, ran_fake, streamed_fake

# Przebieg grafu krok po kroku (`stream_graph()`) na atrapach węzłów i prawdziwym LangGraphie:
# czy kroki odpowiadają przebiegowi, a stan po ostatnim kroku — wynikowi `run_graph()`.

GRAPHS = graph_modules()


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
async def test_the_last_state_is_the_one_run_graph_gives(
    graph: ModuleType,  # wstrzykiwane przez pytest z listy GRAPHS wyżej
) -> None:
    """Sprawdza, czy stan po ostatnim kroku przebiegu krok po kroku to ten sam stan końcowy, który
    daje przebieg w całości: wynik, rozmowa, źródła, zużycie i log, w każdym grafie. Różnić mogą
    się tylko pomiary czasu wywołań narzędzi.

    Wyłapuje strumień, który kończy na stanie sprzed ostatniego kroku albo składa stan inaczej niż
    `run_graph()`: zdarzenie `result` niosłoby wtedy inną odpowiedź niż JSON tej samej trasy."""
    _, final = await streamed_fake(graph)
    whole    = await ran_fake(graph)

    assert final.model_dump(exclude={"tool_timings"}) == whole.model_dump(exclude={"tool_timings"})


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
async def test_there_is_a_step_for_every_node_call_in_order(
    graph: ModuleType,  # wstrzykiwane przez pytest z listy GRAPHS wyżej
) -> None:
    """Sprawdza, czy kroki przychodzą po jednym na każde wywołanie węzła, w kolejności przebiegu:
    ich wpisy logu złożone razem to log stanu końcowego.

    Wyłapuje strumień, który gubi krok, oddaje go dwa razy albo w złej kolejności: konsola
    przebiegu pokazałaby inny przebieg niż ten, który zapisał graf."""
    steps, final = await streamed_fake(graph)

    assert [entry for step in steps for entry in step.log] == final.log


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
async def test_steps_follow_one_another_in_time(
    graph: ModuleType,  # wstrzykiwane przez pytest z listy GRAPHS wyżej
) -> None:
    """Sprawdza, czy każdy krok zaczyna się nie wcześniej niż poprzedni, a jego czas trwania nie
    jest ujemny.

    Wyłapuje czas liczony od startu przebiegu dla każdego kroku albo początek kroku cofnięty
    w czasie: konsola przebiegu ustawiłaby kroki w złej kolejności i pokazała zawyżone czasy."""
    steps, _ = await streamed_fake(graph)

    assert all(step.duration_ms >= 0 for step in steps)
    assert all(later.started_at >= earlier.started_at for earlier, later in pairwise(steps))


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
async def test_steps_together_take_no_longer_than_the_run(
    graph: ModuleType,  # wstrzykiwane przez pytest z listy GRAPHS wyżej
) -> None:
    """Sprawdza, czy czasy trwania kroków razem nie przekraczają czasu całego przebiegu,
    zmierzonego wokół niego.

    Wyłapuje czas kroku liczony od startu przebiegu zamiast od końca poprzedniego kroku: suma
    rosłaby z kwadratem liczby kroków, a konsola przebiegu pokazywałaby, że późne kroki trwały
    najdłużej, choć tylko na nie czekały."""
    started  = time.perf_counter()
    steps, _ = await streamed_fake(graph)
    elapsed  = (time.perf_counter() - started) * 1000

    assert sum(step.duration_ms for step in steps) <= elapsed


async def test_a_step_starts_where_the_previous_one_ended(
    monkeypatch: pytest.MonkeyPatch,  # wstrzykiwane przez pytest; podmienia anonimizację na wolną
) -> None:
    """Sprawdza, czy przy anonimizacji trwającej 50 ms jej krok trwa co najmniej 50 ms, a następny
    krok zaczyna się co najmniej 50 ms po jej początku.

    Wyłapuje początek kroku, który się nie przesuwa, i czas kroku mierzony od złego momentu:
    konsola przebiegu pokazałaby wszystkie kroki w tej samej chwili albo anonimizację jako
    natychmiastową."""
    anonymizer = FakeAnonymizer()
    anonymize  = anonymizer.anonymize

    async def slow_anonymize(text: str) -> AnonymizedText:
        """Anonimizacja atrapy po 50 ms czekania, jak przy wolnej usłudze."""
        await asyncio.sleep(0.05)

        return await anonymize(text)

    monkeypatch.setattr(anonymizer, "anonymize", slow_anonymize)

    steps, _ = await streamed_fake(gate_close, anonymizer)

    assert steps[0].duration_ms >= 50
    assert steps[1].started_at - steps[0].started_at >= timedelta(milliseconds=50)


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
async def test_only_model_turns_carry_usage(
    graph: ModuleType,  # wstrzykiwane przez pytest z listy GRAPHS wyżej
) -> None:
    """Sprawdza, czy zużycie modelu niesie każdy krok tury modelu (`agent`) i żaden inny.

    Wyłapuje zużycie przypisane innemu krokowi albo zgubione przy turze: konsola przebiegu
    pokazałaby koszt przy niewłaściwym wierszu albo tury bez kosztu."""
    steps, _ = await streamed_fake(graph)

    assert [step.usage is not None for step in steps] == [step.node == "agent" for step in steps]


async def test_tool_steps_carry_the_calls_with_arguments_and_results() -> None:
    """Sprawdza, czy w grafie `search` kroki narzędzi niosą wykonane wywołania: najpierw
    wyszukanie, potem odczyt kart, każde z argumentami, które podał model, i z wynikiem, który
    model dostał w rozmowie.

    Wyłapuje kroki narzędzi bez wywołań albo z argumentami lub wynikiem innego wywołania: konsola
    przebiegu nie pokazałaby, o co agent pytał i co mu odpowiedziano."""
    steps, final = await streamed_fake(search)
    runs         = [run for step in steps for run in step.tool_calls]
    results      = {message.call_id: message.content for message in final.messages
                    if message.role == "tool"}

    assert [run.tool for run in runs]      == ["find_tickets_vector", "read_tickets_card"]
    assert [run.arguments for run in runs] == [FAKE_SEARCH_ARGUMENTS, FAKE_READ_ARGUMENTS]
    assert [run.result for run in runs]    == [results[run.call_id] for run in runs]
