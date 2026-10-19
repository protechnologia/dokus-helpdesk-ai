from app.agent_graphs import suggest_handoff, suggest_questions, suggest_solution
from app.entry_routers.suggest.mapping import to_suggest_response
from tests._helpers.routers.samples import LOG, NOTES, PROPOSAL, SOURCE, USAGE, final_state


def test_a_full_proposal_gives_text_and_notes() -> None:
    """Sprawdza, czy pełna propozycja daje w odpowiedzi treść dla klienta i uwagi dla wdrożeniowca
    znak w znak, obok wariantu podanego przez trasę i przeczytanych źródeł.

    Wyłapuje mapowanie, które gubi treść albo uwagi, myli je ze sobą albo zapisuje wariant inny
    niż kliknięty: wdrożeniowiec dostałby do wysłania klientowi notatki z nazwami z kodu."""
    final = final_state(suggest_questions, output=PROPOSAL, sources=[SOURCE])

    response = to_suggest_response(final, "questions")

    assert response.variant                            == "questions"
    assert response.text                               == PROPOSAL.text
    assert response.internal_notes                     == PROPOSAL.internal_notes
    assert [item.item_id for item in response.sources] == [SOURCE.item_id]


def test_notes_alone_give_no_text_and_keep_the_notes() -> None:
    """Sprawdza, czy same uwagi (wariant wymagający źródeł bez odczytanych źródeł albo pytania,
    których już nie trzeba) dają w odpowiedzi `text` równe `None` i uwagi znak w znak.

    Wyłapuje odpowiedź z pustym napisem albo formułką w miejscu `None`, albo bez uwag: helpdesk
    rozpoznaje brak treści dla klienta po `null`, a uwagi mówią, czego agent szukał."""
    response = to_suggest_response(final_state(suggest_solution, output=NOTES), "solution")

    assert response.text           is None
    assert response.internal_notes == NOTES.internal_notes


def test_a_graph_without_output_gives_neither_text_nor_notes() -> None:
    """Sprawdza, czy stan końcowy bez wyniku daje odpowiedź bez treści dla klienta (`None`)
    i z pustymi uwagami, zamiast kończyć się wyjątkiem.

    Wyłapuje mapowanie, które sięga po pole wyniku bez sprawdzenia, czy wynik jest: sprawa bez
    źródeł w grafie, który nie zostawia uwag, kończyłaby się błędem serwera zamiast odpowiedzią
    „nowy typ problemu"."""
    response = to_suggest_response(final_state(suggest_solution, output=None), "solution")

    assert response.text           is None
    assert response.internal_notes == ""


def test_a_variant_without_knowledge_tools_has_no_sources() -> None:
    """Sprawdza, czy wariant, którego stan nie ma pola `sources` (przekazanie sprawy), daje
    odpowiedź z pustą listą źródeł.

    Wyłapuje mapowanie, które zakłada listę źródeł w każdym stanie: przekazanie sprawy kończyłoby
    się błędem serwera, choć pusta lista jest tu informacją, a nie brakiem danych."""
    response = to_suggest_response(final_state(suggest_handoff, output=PROPOSAL), "handoff")

    assert response.sources == []


def test_the_response_carries_usage_and_log_of_the_run() -> None:
    """Sprawdza, czy odpowiedź `/suggest` niesie zużycie modelu i log przebiegu ze stanu końcowego
    grafu, w kolejności wpisów.

    Wyłapuje odpowiedź z zużyciem albo logiem pustym zamiast przebiegu: wołający nie widziałby
    kosztu ani kroków sprawy bez sięgania do logów usługi."""
    response = to_suggest_response(final_state(suggest_questions, output=PROPOSAL), "questions")

    assert response.usage.llm_calls             == USAGE.calls
    assert [item.node for item in response.log] == [entry.node for entry in LOG]
