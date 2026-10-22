import pytest

from anonymizer_app.agent_graphs.anonymize.state import AnonymizeState
from anonymizer_app.agent_nodes.find_addresses.node import (
    FindAddressesNode,
    place_address,
    place_addresses,
)
from anonymizer_app.core_errors.llm_error import LLMError
from tests._helpers.anonymizer_llm import ADDRESSES_SCHEMA, scripted_llm


def replaced(
    text:  str,        # np. "Mieszka na brzozowej 12\nw sulejowie."
    items: list[str],  # np. ["brzozowej 12", "sulejowie"]
) -> list[str]:
    """
    Description:
    Fragmenty tekstu, które węzeł adresów zamieniłby dla podanej odpowiedzi modelu, w kolejności
    tekstu, bez powtórzeń.

    Example args:
        text="Mieszka na brzozowej 12"
        items=["brzozowej 12"]

    Example result:
        ["brzozowej 12"]
    """
    found = place_addresses(text, items)

    return sorted({text[place.start:place.end] for place in found}, key=text.find)


@pytest.mark.parametrize(
    ("text", "fragment", "expected"),
    [
        ("Adres: Zielona  4/2,\tGarwolin.", "Zielona 4/2, Garwolin", ["Zielona  4/2,\tGarwolin"]),
        ("na lipowej 3 w otwocku", "Lipowej 3 w Otwocku", ["lipowej 3 w otwocku"]),
        ("Kasztanowa 7\nPiaseczno", "Kasztanowa 7, Piaseczno", ["Kasztanowa 7", "Piaseczno"]),
        ("mieszka na brzozowej 12 w sulejowie", "Brzozowa 12", ["brzozowej 12"]),
    ],
    ids=["odstępy", "wielkość-liter", "części", "odmiana"],
)
def test_place_address_finds_the_fragment_by_each_way(
    text:     str,
    fragment: str,
    expected: list[str],
) -> None:
    """Sprawdza każdą drogę dopasowania adresu: dosłownie z innymi odstępami, bez względu na
    wielkość liter, częściami między przecinkami i liniami oraz po początku słów, gdy model podał
    adres w mianowniku.

    Wyłapuje adres, który model wskazał, a kod nie znalazł w tekście: przeszedłby dalej, choć
    model go widział."""
    assert [text[start:end] for start, end in place_address(text, fragment)] == expected


def test_marker_and_postal_code_fragments_are_dropped() -> None:
    """Sprawdza, czy fragment ze znacznikiem („ul. {ADRES}”) i sam kod pocztowy niczego nie
    zamieniają.

    Wyłapuje utratę filtrów z sondy: model powtarza adres zamieniony już przez wzorce, a kod
    pocztowy sam nie wskazuje osoby i stoi też w polach wyszukiwania."""
    text = "Pismo z ul. {ADRES} wróciło, w polu wpisano 05-400."

    assert replaced(text, ["ul. {ADRES}", "05-400"]) == []


@pytest.mark.parametrize(
    ("text", "items", "expected"),
    [
        ("Adres: Garwolin, Kościelna 8.", ["Garwolin", "Kościelna 8"], ["Garwolin", "Kościelna 8"]),
        ("Adres:\nKasztanowa 7\nPiaseczno", ["Kasztanowa 7", "Piaseczno"],
         ["Kasztanowa 7", "Piaseczno"]),
        ("Urząd Skarbowy w Toruniu przyjął pismo.", ["Urząd Skarbowy w Toruniu"], []),
        ("Kasztanowa 7\n\n\nPiaseczno ma nowy urząd.", ["Kasztanowa 7", "Piaseczno"],
         ["Kasztanowa 7"]),
    ],
    ids=["styka-się", "linia-obok", "urząd-bez-ulicy", "daleko-od-ulicy"],
)
def test_a_place_without_digit_stays_only_next_to_a_street_with_number(
    text:     str,
    items:    list[str],
    expected: list[str],
) -> None:
    """Sprawdza, czy miejsce bez cyfry zamienia się tylko wtedy, gdy styka się z ulicą z numerem
    albo stoi w linii tuż obok niej, a nazwa urzędu i miejscowość daleko od adresu zostają.

    Wyłapuje utratę filtra, który w sondzie zatrzymał 9 fragmentów bez cyfry w próbce korpusu,
    w tym nazwę urzędu, którą model brał za adres."""
    assert replaced(text, items) == expected


def test_a_non_string_item_is_an_error() -> None:
    """Sprawdza, czy element odpowiedzi, który nie jest napisem, kończy się `LLMError`.

    Wyłapuje pominięcie takiego elementu po cichu: pominięty element to adres, który przeszedłby
    do modelu zewnętrznego."""
    with pytest.raises(LLMError):
        place_addresses("Wierzbowa 6", [{"adres": "Wierzbowa 6"}])


async def test_the_node_asks_every_chunk_and_logs_counts() -> None:
    """Sprawdza, czy węzeł pyta model o każdą część ze schematem adresów, zapisuje miejsca
    w `addresses` jako rodzaj ADRES, a w logu podaje same liczby.

    Wyłapuje węzeł, który pyta schematem osób albo gubi adres wskazany w drugiej części."""
    seen: list = []
    text  = "Proszę wysłać na Wierzbowa 6, Kutno."
    llm   = scripted_llm(addresses=["Wierzbowa 6, Kutno"], seen=seen)
    state = AnonymizeState(input_text=text, after_patterns=text, chunks=["a", "b"])

    update = await FindAddressesNode(llm).run(state)

    schemas = [body["response_format"]["json_schema"]["name"] for body in seen]

    assert schemas == [ADDRESSES_SCHEMA] * 2
    assert [(place.kind, text[place.start:place.end]) for place in update["addresses"]] == [
        ("ADRES", "Wierzbowa 6, Kutno"),
    ]
    assert update["log"][0].message == "2 fragmentów → 1 miejsc"


async def test_an_answer_cut_by_the_token_limit_is_still_read() -> None:
    """Sprawdza, czy węzeł adresów przyjmuje odpowiedź uciętą limitem tokenów i zamienia adresy,
    które w niej stoją.

    Wyłapuje odrzucanie uciętych odpowiedzi także tutaj: model zapętla listę adresów, więc
    zgłoszenia bez żadnej straty kończyłyby się błędem."""
    text  = "Proszę wysłać na Wierzbowa 6, Kutno."
    llm   = scripted_llm(addresses=["Wierzbowa 6, Kutno"], finish_reason="length")
    state = AnonymizeState(input_text=text, after_patterns=text, chunks=["a"])

    update = await FindAddressesNode(llm).run(state)

    assert [text[place.start:place.end] for place in update["addresses"]] == ["Wierzbowa 6, Kutno"]
