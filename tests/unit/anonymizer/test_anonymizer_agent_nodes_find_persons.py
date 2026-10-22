import pytest

from anonymizer_app.agent_graphs.anonymize.state import AnonymizeState
from anonymizer_app.agent_nodes.find_persons.node import (
    PERSON_KINDS,
    FindPersonsNode,
    place_persons,
)
from anonymizer_app.core_errors.llm_error import LLMError
from tests._helpers.anonymizer_llm import PERSONS_SCHEMA, scripted_llm

# Nazwy, które nie są osobami, w kształcie pliku `exceptions.json`.
EXCEPTIONS = ["Dokus", "e-Doręczenia"]

# Wątek w kształcie `RawTicket.as_thread()` po wzorcach: etykieta z rolą, osoba w nagłówku maila,
# w zwrocie i w innej odmianie niż ta, którą poda model.
THREAD = (
    "KOMENTARZ 1 — konsultant, 2026-05-12 10:14:03 (typ: komentarz):\n"
    "Od: Bogumił Cieślak <{EMAIL}>\n"
    "Pani Bronisławo, rozmawiałem z p. Cieślakiem o module Kancelaria."
)


def replaced(
    text:  str,         # np. THREAD
    items: list[dict],  # np. [{"tekst": "Cieślak", "rodzaj": "NAZWISKO"}]
) -> list[str]:
    """
    Description:
    Fragmenty tekstu, które węzeł osób zamieniłby dla podanej odpowiedzi modelu, w kolejności
    tekstu, bez powtórzeń.

    Example args:
        text="Pan Cieślak dzwonił."
        items=[{"tekst": "Cieślak", "rodzaj": "NAZWISKO"}]

    Example result:
        ["Cieślak"]
    """
    found = place_persons(text, items, EXCEPTIONS)

    return sorted({text[place.start:place.end] for place in found}, key=text.find)


def test_a_named_person_is_replaced_in_every_form() -> None:
    """Sprawdza, czy nazwisko wskazane przez model w jednej formie („Cieślak”) zamienia się także
    w innej („Cieślakiem”), a imię w wołaczu — tam, gdzie stoi.

    Wyłapuje utratę rozprowadzenia odmian: osoba, którą model wskazał w mianowniku albo w jednym
    miejscu, przeciekałaby wszędzie tam, gdzie stoi w innej formie."""
    items = [
        {"tekst": "Bogumił",    "rodzaj": "IMIĘ"},
        {"tekst": "Cieślak",    "rodzaj": "NAZWISKO"},
        {"tekst": "Bronisławo", "rodzaj": "IMIĘ"},
    ]

    assert replaced(THREAD, items) == ["Bogumił", "Cieślak", "Bronisławo", "Cieślakiem"]


def test_labels_courtesy_words_and_roles_stay() -> None:
    """Sprawdza, czy zwrot („Pani”) i rola z etykiety („konsultant”) zostają, nawet gdy model je
    wskazał, a słowa w linii etykiety wątku nie są zamieniane.

    Wyłapuje model, który bierze zwrot albo rolę za osobę: zamiana zniszczyłaby etykiety wątku,
    po których graf w `api` rozpoznaje, kto pisał."""
    items = [
        {"tekst": "Pani",       "rodzaj": "IMIĘ"},
        {"tekst": "konsultant", "rodzaj": "NAZWISKO"},
    ]

    assert replaced(THREAD, items) == []


def test_an_exception_and_its_forms_stay_even_when_the_model_names_them() -> None:
    """Sprawdza, czy nazwa z listy wyjątków („Dokus”, „e-Doręczenia”) i jej odmiany („Dokusie”,
    „dokus”, krótsza „Doręczeń”) zostają, gdy model wskaże je jako nazwisko, a osoba z tej samej
    linii nagłówka znika.

    Wyłapuje filtr, który działa tylko na słowo dosłownie z listy: odmiana z wątku („w Dokusie”)
    dalej zamieniałaby się na `{NAZWISKO}`, a nazwa aplikacji znikałaby z całego zgłoszenia."""
    text  = "Do: Teodor Wach <{EMAIL}>; dokus <{EMAIL}>\nW Dokusie nie widać e-Doręczeń."
    items = [
        {"tekst": "Teodor",   "rodzaj": "IMIĘ"},
        {"tekst": "Wach",     "rodzaj": "NAZWISKO"},
        {"tekst": "dokus",    "rodzaj": "NAZWISKO"},
        {"tekst": "Dokusie",  "rodzaj": "NAZWISKO"},
        {"tekst": "Doręczeń", "rodzaj": "NAZWISKO"},
    ]

    assert replaced(text, items) == ["Teodor", "Wach"]


def test_a_marker_is_never_a_person() -> None:
    """Sprawdza, czy fragment, który jest znacznikiem albo stoi w nim, nie zamienia niczego.

    Wyłapuje zamianę słowa ze znacznika („EMAIL”) na znacznik osoby, co psuje wynik wzorców."""
    assert replaced(THREAD, [{"tekst": "{EMAIL}", "rodzaj": "NAZWISKO"},
                             {"tekst": "EMAIL", "rodzaj": "NAZWISKO"}]) == []


@pytest.mark.parametrize(
    "item",
    [{"tekst": "Cieślak"}, {"tekst": "Cieślak", "rodzaj": "OSOBA"}, "Cieślak", {"rodzaj": "IMIĘ"}],
    ids=["bez-rodzaju", "obcy-rodzaj", "napis", "bez-tekstu"],
)
def test_an_item_outside_the_schema_is_an_error(item: object) -> None:
    """Sprawdza, czy element odpowiedzi bez rodzaju, z rodzajem spoza `PERSON_KINDS`, będący
    napisem albo bez tekstu kończy się `LLMError`.

    Wyłapuje pominięcie takiego elementu po cichu: pominięty element to osoba, która przeszłaby
    do modelu zewnętrznego."""
    with pytest.raises(LLMError):
        place_persons(THREAD, [item], EXCEPTIONS)


def test_an_empty_fragment_is_skipped() -> None:
    """Sprawdza, czy pusty fragment odpada bez błędu i niczego nie zamienia.

    Wyłapuje pusty fragment dopasowany do każdej granicy słowa w tekście."""
    assert replaced(THREAD, [{"tekst": " ", "rodzaj": "IMIĘ"}]) == []


async def test_the_node_asks_every_chunk_and_logs_counts() -> None:
    """Sprawdza, czy węzeł pyta model o każdą część tekstu ze schematem osób, zapisuje miejsca
    w całym tekście w `persons`, a w logu podaje same liczby: fragmenty od modelu i miejsca.

    Wyłapuje węzeł, który pyta tylko o pierwszą część długiego wątku, miejsca zdublowane, gdy
    model wskazał tę samą osobę w dwóch częściach, i log, w którym stoi fragment zgłoszenia."""
    seen: list = []
    llm   = scripted_llm(persons=[{"tekst": "Cieślak", "rodzaj": "NAZWISKO"}], seen=seen)
    state = AnonymizeState(input_text=THREAD, after_patterns=THREAD, chunks=["część 1", "cz. 2"])

    update = await FindPersonsNode(llm).run(state)

    schemas = [body["response_format"]["json_schema"]["name"] for body in seen]
    places  = [THREAD[place.start:place.end] for place in update["persons"]]

    assert schemas == [PERSONS_SCHEMA] * 2
    assert sorted(places) == ["Cieślak", "Cieślakiem"]
    assert update["log"][0].message == "2 fragmentów → 2 miejsc"
    assert set(PERSON_KINDS) >= {place.kind for place in update["persons"]}


async def test_an_answer_cut_by_the_token_limit_is_an_error() -> None:
    """Sprawdza, czy odpowiedź uciętą limitem tokenów węzeł osób odrzuca błędem `LLMError`,
    także gdy jej treść jest poprawnym JSON-em.

    Wyłapuje przyjęcie uciętej listy: nazwiska, których model nie zdążył wypisać przed limitem,
    przeszłyby niezamienione do modelu zewnętrznego."""
    llm   = scripted_llm(persons=[{"tekst": "Cieślak", "rodzaj": "NAZWISKO"}],
                         finish_reason="length")
    state = AnonymizeState(input_text=THREAD, after_patterns=THREAD, chunks=["część 1"])

    with pytest.raises(LLMError):
        await FindPersonsNode(llm).run(state)
