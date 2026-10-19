import pytest

from anonymizer_app.core_errors.llm_error import LLMError
from anonymizer_app.core_model.llm_answer import LLMAnswer
from anonymizer_app.engine_llm import answer_items


def answer(
    content:   str,   # np. '{"adresy": ["Wierzbowa 6"]}'
    truncated: bool,  # np. False
) -> LLMAnswer:
    """
    Description:
    Odpowiedź modelu o podanej treści; liczby zużycia nie mają tu znaczenia.

    Example args:
        content='{"adresy": []}'
        truncated=False

    Example result:
        LLMAnswer(content='{"adresy": []}', truncated=False, prompt_tokens=0, …)
    """
    return LLMAnswer(content=content, truncated=truncated, prompt_tokens=0, completion_tokens=0,
                     latency_ms=0.0)


def test_a_full_answer_gives_its_list() -> None:
    """Sprawdza, czy z pełnej odpowiedzi wraca lista spod podanego klucza, w kolejności.

    Wyłapuje odczyt innego klucza albo zgubienie elementów pełnej odpowiedzi."""
    items = answer_items(answer('{"adresy": ["Wierzbowa 6", "Kutno"]}', False), "adresy")

    assert items == ["Wierzbowa 6", "Kutno"]


@pytest.mark.parametrize(
    ("content", "key", "expected"),
    [
        ('{"adresy": ["Wierzbowa 6", "ul. {ADRES}", "ul. {AD', "adresy",
         ["Wierzbowa 6", "ul. {ADRES}"]),
        ('{"dane": [{"tekst": "Leszek", "rodzaj": "IMIĘ"}, {"tekst": "Dud', "dane",
         [{"tekst": "Leszek", "rodzaj": "IMIĘ"}]),
        ('{"adresy": ["Wierz', "adresy", []),
        ('{"adresy": [', "adresy", []),
    ],
    ids=["napisy", "obiekty", "pierwszy-urwany", "pusta-lista"],
)
def test_a_truncated_answer_gives_its_complete_items(
    content:  str,
    key:      str,
    expected: list,
) -> None:
    """Sprawdza, czy z odpowiedzi uciętej limitem tokenów wracają pełne elementy sprzed ucięcia
    — napisy i obiekty — a element urwany w połowie odpada.

    Wyłapuje utratę wszystkich wskazanych danych przez to, że ucięta odpowiedź nie jest pełnym
    JSON-em: na dwóch wątkach próbki korpusu model zapętlał listę adresów, aż limit ją uciął."""
    assert answer_items(answer(content, True), key) == expected


@pytest.mark.parametrize(
    ("content", "truncated"),
    [
        ('{"adresy": ["Wierz', False),
        ('{"dane": []}', False),
        ('["Wierzbowa 6"]', False),
        ('{"dane": ["Wierz', True),
    ],
    ids=["niepełny-bez-ucięcia", "inny-klucz", "nie-obiekt", "ucięty-bez-klucza"],
)
def test_an_answer_outside_the_schema_is_an_error(content: str, truncated: bool) -> None:
    """Sprawdza, czy odpowiedź, która nie jest JSON-em ze schematu, kończy się `LLMError`:
    niepełny JSON bez ucięcia, inny klucz, lista zamiast obiektu i ucięta odpowiedź bez listy
    pod kluczem.

    Wyłapuje odczyt takiej odpowiedzi jako pustej listy: pusta lista znaczy „w tekście nie ma
    danych”, więc dane przeszłyby dalej bez żadnego sygnału."""
    with pytest.raises(LLMError):
        answer_items(answer(content, truncated), "adresy")
