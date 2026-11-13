import pytest

from app.agent_graphs.parse_ticket import (
    FILLED_BY_GRAPH,
    example_state,
    filled_by_graph,
    prompt_digest,
    respond_tool,
    user_prompt,
)
from app.agent_graphs.parse_ticket import graph as graph_module
from app.agent_graphs.parse_ticket.graph import build_parse_prompt
from app.engine_anonymization import AnonymizedText


def test_the_graph_prompt_is_the_parsing_prompt_with_the_anonymized_thread() -> None:
    """Sprawdza, czy tura użytkownika grafu parsującego to prompt parsujący zbudowany z wątku po
    anonimizacji (tu „ZGŁOSZENIE 1") i ze słownika rozstrzygnięć zapisanego w stanie grafu.

    Wyłapuje graf, który składa turę użytkownika inaczej niż funkcja budująca prompt parsujący albo
    bierze wątek czy słownik z innego miejsca: karty zgłoszeń powstawałyby wtedy innym promptem niż
    ten, którego pilnuje test-strażnik."""
    state = example_state().model_copy(update={"anonymized": AnonymizedText(text="ZGŁOSZENIE 1")})

    assert user_prompt(state) == build_parse_prompt("ZGŁOSZENIE 1", state.vocabulary)


def test_the_model_is_not_asked_for_what_the_graph_fills() -> None:
    """Sprawdza, czy schemat narzędzia odpowiedzi grafu parsującego nie ma pól, które wypełnia graf:
    numeru zgłoszenia, daty, wersji słownika rozstrzygnięć i nazwy modelu.

    Wyłapuje schemat, w którym model mógłby te pola podać, czyli je wymyślić: mają pochodzić ze
    stanu grafu, a nie z odpowiedzi modelu."""
    assert not set(FILLED_BY_GRAPH) & set(respond_tool().parameters["properties"])


def test_the_graph_fills_exactly_what_the_model_is_not_asked_for() -> None:
    """Sprawdza, czy graf parsujący dokłada do karty dokładnie te pola, o które model nie jest
    pytany, i bierze je ze stanu: numer zgłoszenia, datę, wersję słownika rozstrzygnięć i nazwę
    modelu, który odpowiedział w ostatniej turze.

    Wyłapuje pole wycięte ze schematu narzędzia odpowiedzi, którego nikt potem nie wypełnia:
    każda karta byłaby wtedy odrzucana jako niepełna, a model nie miałby jak tego poprawić."""
    state  = example_state().model_copy(update={"model": "gpt-6.1-sol"})
    filled = filled_by_graph(state)

    assert set(filled) == set(FILLED_BY_GRAPH)
    assert filled      == {
        "ticket_id":                     state.ticket_id,
        "date":                          state.date,
        "resolution_vocabulary_version": state.vocabulary.version,
        "parser_model":                  "gpt-6.1-sol",
    }


def test_the_prompt_digest_is_a_stable_sha256() -> None:
    """Sprawdza, czy skrót promptu parsującego to 64 znaki szesnastkowe i czy dwa wywołania na tym
    samym prompcie dają ten sam skrót.

    Wyłapuje skrót, który zmienia się między wywołaniami (np. przez kolejność kluczy albo datę):
    dwa raporty importu na tym samym prompcie wyglądałyby jak dwie wersje kontraktu."""
    first = prompt_digest()

    assert len(first) == 64
    assert int(first, 16) >= 0
    assert prompt_digest() == first


@pytest.mark.parametrize(
    "part",
    [
        pytest.param("system_prompt",   id="prompt-systemowy"),
        pytest.param("prompt_template", id="szablon-tury-uzytkownika"),
        pytest.param("respond_tool",    id="narzedzie-odpowiedzi"),
    ],
)
def test_the_prompt_digest_follows_every_part_of_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
    part:        str,
) -> None:
    """Sprawdza, czy skrót promptu parsującego zmienia się po zmianie każdej z trzech części,
    które model dostaje poza danymi: promptu systemowego, szablonu tury użytkownika i definicji
    narzędzia odpowiedzi.

    Wyłapuje skrót liczony z części kontraktu: karty z dwóch różnych promptów miałyby w raportach
    importu ten sam skrót i nie dałoby się ich rozróżnić."""
    before   = prompt_digest()
    original = getattr(graph_module, part)

    if part == "respond_tool":
        changed = lambda: original().model_copy(update={"description": "zmieniony opis"})  # noqa: E731
    else:
        changed = lambda: original() + "\n- zmieniona zasada"  # noqa: E731

    monkeypatch.setattr(graph_module, part, changed)

    assert prompt_digest() != before
