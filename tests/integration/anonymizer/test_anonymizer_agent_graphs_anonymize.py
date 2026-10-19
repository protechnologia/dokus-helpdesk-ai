import logging

import pytest

from anonymizer_app.core_engine import AgentEngine
from anonymizer_app.core_errors.llm_error import LLMError
from tests._helpers.anonymization import ANONYMIZED_TEXT, RAW_TEXT, SENSITIVE
from tests._helpers.anonymizer_llm import (
    ADDRESSES_SCHEMA,
    PERSONS_SCHEMA,
    model_client_on,
    scripted_llm,
)
from tests._helpers.transport import always

# Odpowiedź modelu na `RAW_TEXT`: osoba słowo po słowie, adresu nie ma.
RAW_TEXT_PERSONS = [
    {"tekst": "Jan",   "rodzaj": "IMIĘ"},
    {"tekst": "Nowak", "rodzaj": "NAZWISKO"},
]

# Kolejność węzłów w logu przebiegu: dwa środkowe biegną równolegle, więc stoją w dowolnej.
FIRST_NODES = ["replace_patterns", "split_chunks"]
MODEL_NODES = {"find_persons", "find_addresses"}
LAST_NODE   = "replace_found"


async def test_the_graph_replaces_patterns_persons_and_addresses() -> None:
    """Sprawdza, czy silnik `agent` na grafie anonimizacji zamienia telefon wzorcem, a osobę
    wskazaną przez model — znacznikami rodzaju, i oddaje tekst ze znacznikami w całości.

    Wyłapuje graf, który gubi wynik któregoś węzła (na przykład zamienia osoby w tekście sprzed
    wzorców i przywraca przez to telefon), albo krawędź, przez którą `replace_found` rusza
    przed węzłem z modelem."""
    engine = AgentEngine(scripted_llm(persons=RAW_TEXT_PERSONS))

    assert await engine.anonymize(RAW_TEXT) == ANONYMIZED_TEXT


async def test_the_run_log_lists_every_node_in_order() -> None:
    """Sprawdza, czy log przebiegu ma po jednym wpisie od każdego węzła: najpierw wzorce i podział
    na części, potem oba węzły z modelem w dowolnej kolejności, na końcu zamiana miejsc — i czy
    oba węzły z modelem zapytały model, każdy swoim schematem.

    Wyłapuje graf bez któregoś kroku albo z krokami w złej kolejności: kolejne kroki anonimizacji
    mają być widoczne w logu usługi, a pominięty węzeł adresów przepuściłby adres bez kotwicy."""
    seen: list = []
    engine = AgentEngine(scripted_llm(persons=RAW_TEXT_PERSONS, seen=seen))

    final = await engine.run_graph(RAW_TEXT)
    nodes = [entry.node for entry in final.log]

    assert nodes[:2]       == FIRST_NODES
    assert set(nodes[2:4]) == MODEL_NODES
    assert nodes[4:]       == [LAST_NODE]
    assert sorted(body["response_format"]["json_schema"]["name"] for body in seen) == sorted(
        [ADDRESSES_SCHEMA, PERSONS_SCHEMA],
    )


async def test_an_address_beats_a_person_on_the_same_words() -> None:
    """Sprawdza, czy adres, który model wskazał razem z ulicą nazwaną od osoby, znika w całości
    jako `{ADRES}`, choć węzeł osób wziął słowo z ulicy za nazwisko.

    Wyłapuje zamianę nazwiska wewnątrz adresu: zostałaby reszta adresu, z numerem domu."""
    text   = "Decyzja trafiła na Kościuszki 8/2, Tarnów."
    llm    = scripted_llm(
        persons   = [{"tekst": "Kościuszki", "rodzaj": "NAZWISKO"}],
        addresses = ["Kościuszki 8/2, Tarnów"],
    )

    assert await AgentEngine(llm).anonymize(text) == "Decyzja trafiła na {ADRES}."


async def test_a_model_failure_stops_the_graph() -> None:
    """Sprawdza, czy awaria serwera modelu (502 pośrednika przy wyłączonym podzie) kończy przebieg
    grafu błędem `LLMError`, bez wyniku.

    Wyłapuje graf, który przy awarii jednego węzła oddaje tekst po samych wzorcach: imiona
    i nazwiska poszłyby wtedy do modelu zewnętrznego (fail-closed)."""
    engine = AgentEngine(model_client_on(always({"error": "pod down"}, status=502)))

    with pytest.raises(LLMError):
        await engine.anonymize(RAW_TEXT)


async def test_the_log_carries_numbers_not_text(caplog: pytest.LogCaptureFixture) -> None:
    """Sprawdza, czy ani log przebiegu w stanie grafu, ani log usługi na żadnym poziomie (także
    DEBUG) nie niesie fragmentu zgłoszenia — a przebieg krok po kroku w logu usługi jest.

    Wyłapuje wpis kroku z fragmentem tekstu albo zapis stanu grafu: wejściem usługi jest surowe
    zgłoszenie, a log nie może go zapisać nigdzie."""
    caplog.set_level(logging.DEBUG)
    engine = AgentEngine(scripted_llm(persons=RAW_TEXT_PERSONS))

    final = await engine.run_graph(RAW_TEXT)
    await engine.anonymize(RAW_TEXT)

    for fragment in SENSITIVE:
        assert all(fragment not in entry.message for entry in final.log)
        assert fragment not in caplog.text
    assert "anonymize_step node=find_persons" in caplog.text


async def test_aclose_closes_the_model_client() -> None:
    """Sprawdza, czy zamknięcie silnika zamyka połączenia z modelem.

    Wyłapuje silnik, który przy wyłączaniu usługi zostawia otwarte połączenia do serwera
    modelu."""
    llm    = scripted_llm()
    engine = AgentEngine(llm)

    await engine.aclose()

    assert llm._client.is_closed

