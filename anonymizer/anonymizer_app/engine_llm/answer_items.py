"""
Description:
Odczyt listy z odpowiedzi modelu w schemacie JSON — także z odpowiedzi, którą urwał limit
tokenów. Model zdarza się zapętlić i powtarzać jeden fragment, aż limit go zatrzyma; ucięta
odpowiedź to niepełny JSON, a bez odczytu pełnych elementów sprzed ucięcia wątek straciłby
wszystkie wskazane dane.

Przykład (odpowiedź ucięta w połowie trzeciego elementu):

    przed: '{"adresy": ["Akacjową 9/1, Węgrów", "ul. {ADRES}", "ul. {AD'
    po:    ["Akacjową 9/1, Węgrów", "ul. {ADRES}"]

Kroki:

1. Cała treść czyta się jako JSON; lista pod kluczem wraca od razu.
2. Treść, która nie jest JSON-em, czyta się dalej tylko wtedy, gdy limit tokenów ją uciął:
   od nawiasu otwierającego listę bierze się kolejne pełne wartości, aż do pierwszej niepełnej.
3. Każdy inny przypadek to `LLMError`: odpowiedź poza schematem nie może po cichu dać pustej
   listy, bo pusta lista znaczy „w tekście nie ma danych".

O czym pamiętać przy zmianach:

- Ucięcie zawsze odcina koniec listy, więc pełne elementy sprzed niego są tym, co model
  naprawdę wskazał. Czego nie zdążył wskazać, wołający nie odzyska; liczy to log węzła.
"""

import json
from typing import Any

from anonymizer_app.core_errors.llm_error import LLMError
from anonymizer_app.core_model.llm_answer import LLMAnswer

_DECODER = json.JSONDecoder()


def answer_items(
    answer: LLMAnswer,  # np. LLMAnswer(content='{"adresy": ["Wierzbowa 6"]}', truncated=False, …)
    key:    str,        # np. "adresy"
) -> list[Any]:
    """
    Description:
    Lista pod kluczem z odpowiedzi modelu; z odpowiedzi uciętej — jej pełne elementy.

    Example args:
        answer=LLMAnswer(content='{"adresy": ["Wierzbowa 6", "Ku', truncated=True, …)
        key="adresy"

    Example result:
        ["Wierzbowa 6"]

    Raises:
        LLMError: odpowiedź nie jest JSON-em ze schematu, a limit jej nie uciął, albo ucięta
            odpowiedź nie ma początku listy pod kluczem
    """
    try:
        payload = json.loads(answer.content)
    except json.JSONDecodeError:
        # --- treść niepełna: tylko ucięcie limitem tłumaczy taką odpowiedź ---
        if answer.truncated:
            return _complete_items(answer.content, key)

        raise LLMError("odpowiedź modelu nie jest JSON-em") from None

    items = payload.get(key) if isinstance(payload, dict) else None

    if not isinstance(items, list):
        raise LLMError(f"odpowiedź modelu nie ma listy `{key}`")

    return items


def _complete_items(
    content: str,  # np. '{"adresy": ["Wierzbowa 6", "Ku'
    key:     str,  # np. "adresy"
) -> list[Any]:
    """
    Description:
    Pełne elementy listy pod kluczem z uciętej treści JSON, w kolejności odpowiedzi.

    Example args:
        content='{"dane": [{"tekst": "Leszek", "rodzaj": "IMIĘ"}, {"tekst": "Dud'
        key="dane"

    Example result:
        [{"tekst": "Leszek", "rodzaj": "IMIĘ"}]

    Raises:
        LLMError: w treści nie ma początku listy pod kluczem
    """
    opening = content.find(f'"{key}"')
    start   = content.find("[", opening) if opening >= 0 else -1

    if start < 0:
        raise LLMError(f"ucięta odpowiedź modelu nie ma początku listy `{key}`")

    items: list[Any] = []
    position = start + 1

    while True:
        # Odstępy i przecinki między elementami nie są wartościami.
        while position < len(content) and content[position] in " \t\r\n,":
            position += 1

        try:
            item, position = _DECODER.raw_decode(content, position)
        except json.JSONDecodeError:
            # Element urwany w połowie albo koniec listy: dalej nic pełnego już nie ma.
            return items

        items.append(item)
