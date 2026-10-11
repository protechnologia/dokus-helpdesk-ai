import pytest
from pydantic import ValidationError

from app.agent_graphs import suggest_questions
from app.agent_graphs.suggest_questions import QuestionsAnswer, to_output
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes

# Odpowiedź modelu w grafie `suggest_questions` i jej zamiana na wynik grafu. Kształt grafu,
# narzędzia i zabezpieczenia wspólne dla wszystkich grafów sprawdza test kontraktu grafów.

# Uwagi, jakimi model tłumaczy brak pytań.
NO_QUESTIONS = "Pytań już nie trzeba: klient potwierdził plik blokady (zgł. 90002)."


def test_an_answer_without_questions_is_valid_when_it_is_explained() -> None:
    """Sprawdza, czy odpowiedź modelu bez pytań (`text` równe `null`) z uwagami dla wdrożeniowca
    jest poprawna.

    Wyłapuje walidację, która żąda pytań zawsze: po odpowiedziach klienta, które rozstrzygają
    sprawę, model musiałby układać pytania na siłę albo jego odpowiedź wracałaby do poprawki."""
    answer = QuestionsAnswer(text=None, internal_notes=NO_QUESTIONS)

    assert answer.text is None


@pytest.mark.parametrize("notes", ["", "   "])
def test_an_answer_without_questions_and_without_notes_is_rejected(notes: str) -> None:
    """Sprawdza, czy odpowiedź bez pytań i z pustymi uwagami, także złożonymi z samych spacji,
    daje błąd walidacji.

    Wyłapuje pustą odpowiedź przyjętą jako poprawną: wdrożeniowiec kliknąłby guzik i nie dostał
    ani pytań, ani słowa o tym, dlaczego ich nie ma."""
    with pytest.raises(ValidationError):
        QuestionsAnswer(text=None, internal_notes=notes)


@pytest.mark.parametrize("text", ["", "  \n "])
def test_a_blank_text_means_no_questions(text: str) -> None:
    """Sprawdza, czy pusty napis w miejscu pytań, także z samych białych znaków, jest czytany jak
    brak pytań (`null`), o ile są uwagi.

    Wyłapuje pusty tekst potraktowany jak lista pytań: wołający dostałby propozycję z pustą
    treścią dla klienta zamiast informacji, że pytań już nie trzeba."""
    answer = QuestionsAnswer(text=text, internal_notes=NO_QUESTIONS)

    assert answer.text is None


def test_a_blank_text_without_notes_is_rejected() -> None:
    """Sprawdza, czy pusty napis w miejscu pytań przy pustych uwagach daje błąd walidacji, tak
    samo jak `null`.

    Wyłapuje obejście wymogu uwag pustym tekstem: zamiana pustego tekstu na brak pytań musi
    zajść, zanim sprawdzamy, czy brak pytań jest wytłumaczony."""
    with pytest.raises(ValidationError):
        QuestionsAnswer(text="", internal_notes="")


def test_questions_may_come_without_notes() -> None:
    """Sprawdza, czy lista pytań z pustymi uwagami jest poprawna.

    Wyłapuje wymóg uwag rozciągnięty na każdą odpowiedź: przy zwykłej liście pytań model ma
    prawo nie mieć nic do dodania."""
    answer = QuestionsAnswer(text="1. Od kiedy nie przychodzą przesyłki?", internal_notes="")

    assert answer.text == "1. Od kiedy nie przychodzą przesyłki?"


@pytest.mark.parametrize(
    "arguments",
    [
        {"internal_notes": NO_QUESTIONS},
        {"text": "1. Od kiedy?"},
        {"text": "1. Od kiedy?", "internal_notes": "", "sources": ["90002"]},
    ],
    ids=["bez pola text", "bez pola internal_notes", "z listą źródeł"],
)
def test_the_answer_has_exactly_two_fields(arguments: dict) -> None:
    """Sprawdza, czy odpowiedź modelu bez pola `text`, bez pola `internal_notes` albo z polem
    spoza schematu (tu z listą źródeł) daje błąd walidacji.

    Wyłapuje pole, które model może pominąć (nie dałoby się odróżnić decyzji „pytań nie trzeba"
    od zapomnianego pola), oraz źródła podane przez model zamiast wynikające z odczytów."""
    with pytest.raises(ValidationError):
        QuestionsAnswer.model_validate(arguments)


def test_questions_become_a_proposal() -> None:
    """Sprawdza, czy odpowiedź z listą pytań staje się propozycją z tą samą treścią i tymi samymi
    uwagami.

    Wyłapuje zamianę, która gubi pytania albo uwagi po drodze od odpowiedzi modelu do wyniku
    grafu."""
    answer = QuestionsAnswer(text="1. Od kiedy?", internal_notes="1: odcina zacięcie kolejki")

    assert to_output(answer) == Proposal(**answer.model_dump())


def test_no_questions_become_notes_only() -> None:
    """Sprawdza, czy odpowiedź bez pytań staje się samymi uwagami dla wdrożeniowca, czyli tym
    samym wynikiem, jakim wariant z rozwiązaniem kończy sprawę bez źródeł.

    Wyłapuje brak pytań oddany jako propozycja: wołający nie dostałby wtedy `text` równego
    `null`, po którym rozpoznaje, że nie ma czego wysłać klientowi."""
    answer = QuestionsAnswer(text=None, internal_notes=NO_QUESTIONS)

    assert to_output(answer) == ProposalNotes(internal_notes=NO_QUESTIONS)


def test_the_respond_tool_lets_the_model_give_no_questions() -> None:
    """Sprawdza, czy schemat narzędzia odpowiedzi wymaga pola `text` i dopuszcza w nim `null`,
    a prompt systemowy i opis narzędzia mówią modelowi o tej wartości.

    Wyłapuje schemat i prompt, które się rozjechały: prompt kazałby oddać `null`, którego schemat
    nie przyjmuje, albo schemat pozwalałby na `null`, o którym model nic nie wie."""
    tool = suggest_questions.respond_tool()
    text = tool.parameters["properties"]["text"]

    assert "text" in tool.parameters["required"]
    assert {"type": "null"} in text["anyOf"]
    assert "`null`" in suggest_questions.system_prompt()
    assert "`null`" in tool.description
