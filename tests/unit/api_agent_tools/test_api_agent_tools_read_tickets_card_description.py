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
    """Słownik domyślny → w opisie narzędzia każda klasa z jej znaczeniem: karta niesie samą
    nazwę klasy, a „bez zmian w systemie" prowadzi do innej odpowiedzi niż „naprawione"."""
    description = _in_one_line(FakeReadTicketsCardTool().description)

    for entry in get_resolution_classes().classes:
        assert f"- `{entry.name}`: {_in_one_line(entry.hint)}" in description


def test_the_place_for_the_classes_is_filled_and_the_call_limit_waits() -> None:
    """Opis instancji → bez miejsca na klasy, ale nadal z miejscem na limit wywołań: klasy
    wstawia narzędzie ze słownika, a limit dopiero graf z konfiguracji."""
    description = FakeReadTicketsCardTool().description

    assert RESOLUTION_CLASSES_PLACEHOLDER not in description
    assert "{{max_calls}}" in description
    assert RESOLUTION_CLASSES_PLACEHOLDER in FakeReadTicketsCardTool.description


def test_the_description_follows_the_clients_dictionary() -> None:
    """Słownik innego helpdesku → w opisie jego klasy, a domyślnych nie ma: słownik to dane
    klienta i opis ma się zmieniać razem z nim, bez naszego deployu."""
    description = FakeReadTicketsCardTool(resolution=OTHER).description

    assert "- `zwrot_do_dzialu`: sprawę przekazano do działu merytorycznego" in description
    assert "- `zamkniete`: klient potwierdził, że problem ustąpił" in description
    assert "`bez_zmian_w_systemie`" not in description


def test_one_tool_does_not_change_the_description_of_another() -> None:
    """Dwa narzędzia z różnymi słownikami → każde ma swój opis: opis wypełnia instancja, a opis
    klasy zostaje nietknięty."""
    other   = FakeReadTicketsCardTool(resolution=OTHER)
    default = FakeReadTicketsCardTool()

    assert "`zwrot_do_dzialu`" in other.description
    assert "`zwrot_do_dzialu`" not in default.description


def test_a_long_meaning_wraps_like_the_rest_of_the_description() -> None:
    """Długie znaczenie klasy → zawinięte do szerokości opisu, z wcięciem dalszych linii,
    a nazwa klasy w całości w pierwszej linii: model ma ją rozpoznać w polu `resolution`."""
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
    """Słownik bez klas → jedno zdanie, że klas nie ma, zamiast pustego miejsca pod nagłówkiem:
    produkt działa też bez skonfigurowanego słownika."""
    text = render_resolution_classes(ResolutionVocabulary(version=1, classes=[]))

    assert text == "- słownik nie definiuje żadnej klasy"
