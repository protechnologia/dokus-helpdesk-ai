from app.agent_tools.tickets.read_tickets_card import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_card.base import (
    DESCRIPTION_WIDTH,
    RESOLUTION_CLASSES_PLACEHOLDER,
    render_resolution_classes,
)
from app.core_model.dicts.resolution_class import ResolutionClass
from app.core_model.dicts.resolution_vocabulary import ResolutionVocabulary
from app.core_service.loader_dict_resolution import get_resolution_classes

# Opis `read_tickets_card` dla modelu niesie znaczenie klas rozstrzygnięcia ze słownika klienta.
# Sprawdzamy go na atrapie: wypełnia go klasa wspólna atrapy i narzędzia właściwego.

# Zmyślony słownik innego helpdesku: inne klasy niż w zestawie domyślnym.
OTHER = ResolutionVocabulary(
    version = 7,
    classes = [
        ResolutionClass(name="zwrot_do_dzialu", hint="sprawę przekazano do działu merytorycznego"),
        ResolutionClass(name="zamkniete",       hint="klient potwierdził, że problem ustąpił"),
    ],
)


def _in_one_line(
    text: str,  # np. "- `brak`: z wątku nie\n  wynika…"
) -> str:
    """
    Description:
    Sprowadza tekst do jednej linii, żeby dało się w nim szukać zdania zawiniętego na szerokość.

    Example args:
        text="- `brak`: z wątku nie\\n  wynika, czym sprawa się skończyła"

    Example result:
        "- `brak`: z wątku nie wynika, czym sprawa się skończyła"
    """
    return " ".join(text.split())


def test_the_description_explains_every_class_of_the_dictionary() -> None:
    """Sprawdza, czy opis narzędzia zbudowanego na domyślnym słowniku rozstrzygnięć wymienia każdą
    klasę tego słownika razem z jej znaczeniem.

    Wyłapuje opis, w którym brakuje klasy albo jej objaśnienia: karta niesie samą nazwę klasy,
    a „bez zmian w systemie" prowadzi do innej odpowiedzi niż „naprawione", więc model musi
    wiedzieć, co która znaczy."""
    description = _in_one_line(FakeReadTicketsCardTool().description)

    for entry in get_resolution_classes().classes:
        assert f"- `{entry.name}`: {_in_one_line(entry.hint)}" in description


def test_the_place_for_the_classes_is_filled_and_the_call_limit_waits() -> None:
    """Sprawdza, czy w opisie gotowego narzędzia nie ma już znacznika miejsca na klasy
    rozstrzygnięcia, ale nadal jest znacznik `{{max_calls}}` na limit wywołań. Opis wspólny,
    z którego powstają opisy poszczególnych narzędzi, zachowuje znacznik klas.

    Wyłapuje narzędzie, które nie wstawia klas ze słownika albo przy okazji usuwa miejsce na limit:
    limit wpisuje dopiero graf z konfiguracji, więc model dostałby opis z surowym znacznikiem albo
    bez limitu."""
    description = FakeReadTicketsCardTool().description

    assert RESOLUTION_CLASSES_PLACEHOLDER not in description
    assert "{{max_calls}}" in description
    assert RESOLUTION_CLASSES_PLACEHOLDER in FakeReadTicketsCardTool.description


def test_the_description_follows_the_clients_dictionary() -> None:
    """Sprawdza, czy narzędzie zbudowane na słowniku innego helpdesku ma w opisie jego klasy
    (`zwrot_do_dzialu`, `zamkniete`) z ich znaczeniem, a domyślnej klasy `bez_zmian_w_systemie`
    w opisie nie ma.

    Wyłapuje opis z klasami wpisanymi na stałe: słownik to dane klienta i opis ma się zmieniać razem
    z nim, bez naszego wdrożenia."""
    description = FakeReadTicketsCardTool(resolution=OTHER).description

    assert "- `zwrot_do_dzialu`: sprawę przekazano do działu merytorycznego" in description
    assert "- `zamkniete`: klient potwierdził, że problem ustąpił" in description
    assert "`bez_zmian_w_systemie`" not in description


def test_one_tool_does_not_change_the_description_of_another() -> None:
    """Sprawdza, czy dwa narzędzia zbudowane na różnych słownikach mają każde swój opis: klasa
    `zwrot_do_dzialu` jest w opisie pierwszego, a w opisie drugiego, zbudowanego po nim na słowniku
    domyślnym, jej nie ma.

    Wyłapuje wypełnianie opisu wspólnego dla wszystkich egzemplarzy narzędzia zamiast opisu jednego
    z nich: klasy rozstrzygnięcia z jednego słownika przechodziłyby wtedy do każdego kolejnego
    narzędzia."""
    other   = FakeReadTicketsCardTool(resolution=OTHER)
    default = FakeReadTicketsCardTool()

    assert "`zwrot_do_dzialu`" in other.description
    assert "`zwrot_do_dzialu`" not in default.description


def test_a_long_meaning_wraps_like_the_rest_of_the_description() -> None:
    """Sprawdza, czy długie znaczenie klasy rozstrzygnięcia jest zawijane do szerokości opisu
    narzędzia: nazwa klasy stoi w całości w pierwszej linii, żadna linia nie przekracza szerokości,
    a dalsze linie są wcięte.

    Wyłapuje zawijanie, które dzieli nazwę klasy między linie albo gubi wcięcie: model ma rozpoznać
    tę nazwę w polu `resolution` karty i widzieć, gdzie kończy się opis jednej klasy."""
    long_hint  = "klient działa u siebie " * 8
    vocabulary = ResolutionVocabulary(
        version = 1,
        classes = [ResolutionClass(name="bez_zmian_w_systemie", hint=long_hint)],
    )

    lines = render_resolution_classes(vocabulary).splitlines()

    assert lines[0].startswith("- `bez_zmian_w_systemie`: ")
    assert len(lines) > 1
    assert all(len(line) <= DESCRIPTION_WIDTH for line in lines)
    assert all(line.startswith("  ") for line in lines[1:])


def test_a_dictionary_without_classes_says_so() -> None:
    """Sprawdza, czy dla słownika bez żadnej klasy lista klas w opisie narzędzia to jedno zdanie:
    „słownik nie definiuje żadnej klasy".

    Wyłapuje puste miejsce pod nagłówkiem w opisie: produkt działa też bez skonfigurowanego
    słownika, a model nie wiedziałby, czy klas nie ma, czy opis jest urwany."""
    text = render_resolution_classes(ResolutionVocabulary(version=1, classes=[]))

    assert text == "- słownik nie definiuje żadnej klasy"
