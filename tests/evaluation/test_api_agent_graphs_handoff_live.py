"""
Description:
Scenariusze ewaluacyjne przekazania sprawy na żywym modelu (p. 59): czy wiadomość dla klienta trzyma
układ z przykładu, niesie fakty z wątku i ostrzeżenie, a nie dopisuje ustaleń, obietnic ani treści
z przykładu. Zestaw leży w `data/safe/golden/handoff.json`; każda sprawa to zgłoszenie z listą
faktów, rdzeni ostrzeżenia i pułapek, czyli dopisków, które kuszą model.

Każdy graf z sekcją w zestawie przechodzi przez osiem testów:

| test                                        | co sprawdza                                   |
|---------------------------------------------|-----------------------------------------------|
| `test_every_case_gets_an_accepted_message`  | każda sprawa kończy się wiadomością           |
| `test_the_message_keeps_the_layout`         | powitanie, podsumowanie, przekazanie, pożegnanie |
| `test_facts_from_the_thread_stay`           | żaden fakt z wątku nie ginie                  |
| `test_a_warning_from_the_thread_stays`      | ostrzeżenie z wątku dociera do klienta        |
| `test_nothing_is_added`                     | nie przybywa liczb ani dopisków z pułapek     |
| `test_nothing_is_promised`                  | nie ma obietnic konkretnego działania         |
| `test_the_example_is_not_copied`            | treść przykładu nie trafia do wiadomości      |
| `test_no_marker_is_malformed`               | napisy w klamrach to znaczniki bez odmiany    |

Pomiary:

| graf              | znaleziska            | pomiar                                         |
|-------------------|-----------------------|------------------------------------------------|
| `suggest_handoff` | 0 z 9 w każdym liczniku | 2026-10-30, `gpt-6.1-sol`, w dwóch przebiegach |

O czym pamiętać przy zmianach:

- Progu nie ma: każde znalezisko to poprawka promptu. Sprawę poprawia się tylko wtedy, gdy błędna
  jest ona sama, nigdy pod wynik.
- Listy łapią tylko to, co przewidział autor sprawy: przypuszczenie podane jako ustalenie albo
  zgadywaną przyczynę spoza pułapek pokaże dopiero wiadomość, którą raport wypisuje w całości.
  Czyta się ją przy pierwszym pomiarze i przy każdej zmianie wyniku.
- Graf idzie na atrapie anonimizatora, jak w pozostałych scenariuszach, a sprawa ze znacznikami
  (h08) niesie tekst, który oddała prawdziwa usługa `anonymizer`.
- Ostrzeżenia nie wymusza żadna zasada promptu: w sondzie z 2026-10-30 model przekazał je także
  bez niej (15 z 15 prób na h04 i h09), więc pilnują go tylko te dwie sprawy. Rdzenie są listą:
  przy czerwonym teście najpierw przeczytaj wiadomość, bo brzmienie mogło być po prostu inne.
- KOSZTUJE: sprawa to jedna tura modelu, a `suggest_handoff` ma dziewięć spraw: na `gpt-6.1-sol`
  około 0,03 USD i kilka sekund.
"""


import pytest

from tests._helpers.live import (
    LiveUsageReport,
    live_generation_llm,
    remember_per_graph,
)
from tests._helpers.scenarios.handoff import (
    HandoffOutcomesOf,
    HandoffReport,
    handoff_sections,
    measure_handoff_cases,
)

pytestmark = pytest.mark.llm_live

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = handoff_sections()


@pytest.fixture(scope="module")
def outcomes(
    request:        pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:     LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    handoff_report: HandoffReport,          # wstrzykiwane przez pytest; raport ocen spraw
) -> HandoffOutcomesOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu przeprowadza jego sprawy na żywym modelu i oddaje ich
    oceny. Sprawy grafu liczą się przy pierwszym teście, który o nie poprosi, i są zapamiętane
    na cały plik — razem z błędem, jeśli przebieg się nim skończył.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: outcomes("suggest_handoff") -> [HandoffOutcome(case=HandoffCase(…), …), …]
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(
        lambda name: measure_handoff_cases(name, llm, live_usage, handoff_report)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_case_gets_an_accepted_message(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy każda sprawa przekazania kończy się na żywym modelu wiadomością, którą węzeł
    odpowiedzi przyjął.

    Wyłapuje prompt, przy którym model nie umie oddać wiadomości narzędziem odpowiedzi nawet po
    poprawce: wdrożeniowiec dostaje wtedy błąd zamiast tekstu do wysłania."""
    rejected = [outcome for outcome in outcomes(graph) if outcome.rejected]

    assert not rejected, (
        f"{graph}: bez wiadomości — " + ", ".join(outcome.case.label for outcome in rejected)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_the_message_keeps_the_layout(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy każda wiadomość zaczyna się akapitem „Dzień dobry.”, kończy akapitem
    „Pozdrawiam.”, ma co najmniej cztery akapity, a przedostatni mówi o przekazaniu sprawy.

    Wyłapuje model, który nie trzyma układu z przykładu w opisie pola: wiadomość staje się jednym
    blokiem tekstu, a wdrożeniowiec musi ją układać ręcznie przed wysłaniem."""
    broken = [outcome for outcome in outcomes(graph) if outcome.layout]

    assert not broken, (
        f"{graph}: układ — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in broken)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_facts_from_the_thread_stay(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy każdy fakt z listy sprawy (nazwa usługi, komunikat, liczba, ustalenie) stoi
    w wiadomości; angielski komunikat w oryginale.

    Wyłapuje pustą formułkę o przekazaniu, która nie mówi klientowi, o co chodzi i co już wiadomo,
    oraz komunikat przetłumaczony przez model, którego nie da się potem znaleźć po treści."""
    lost = [outcome for outcome in outcomes(graph) if outcome.lost]

    assert not lost, (
        f"{graph}: zgubione fakty — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in lost)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_a_warning_from_the_thread_stays(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy wiadomość w sprawie, w której wątek mówi, czego klient ma nie robić, powtarza
    to ostrzeżenie.

    Wyłapuje streszczenie, które gubi „proszę nie ponawiać wysyłki”: klient czeka na przekazaną
    sprawę, próbuje jeszcze raz i wykonuje krok, którego nie da się cofnąć."""
    lost = [outcome for outcome in outcomes(graph) if outcome.warning_lost]

    assert not lost, (
        f"{graph}: zgubione ostrzeżenia — " + ", ".join(outcome.case.label for outcome in lost)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_nothing_is_added(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy w żadnej wiadomości nie ma liczby spoza zgłoszenia ani dopisku z pułapek
    sprawy: zgadywanej przyczyny, sprawdzenia, którego nie było, prośby o dane, wymyślonego
    ostrzeżenia.

    Wyłapuje wiadomość, która mówi klientowi coś, czego nikt nie ustalił, na przykład zamienia
    „sprawdzimy” na „sprawdziliśmy” (zasada 9)."""
    added = [outcome for outcome in outcomes(graph) if outcome.new_numbers or outcome.added]

    assert not added, (
        f"{graph}: dopisane — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in added)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_nothing_is_promised(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy żadna wiadomość nie obiecuje konkretnego działania („sprawdzimy”,
    „naprawimy”, „wkrótce”), także gdy zapowiedź stoi w wątku.

    Wyłapuje obietnicę, której nikt nie pilnuje: po przekazaniu sprawy klient czeka na coś, czego
    serwis wcale nie musi zrobić."""
    promised = [outcome for outcome in outcomes(graph) if outcome.promised]

    assert not promised, (
        f"{graph}: obietnice — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in promised)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_the_example_is_not_copied(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy treść przykładu z opisu pola `text` nie trafia do wiadomości, gdy zgłoszenie
    dotyczy czegoś innego.

    Wyłapuje model, który bierze przykład za materiał: klient dostaje wiadomość o podpisie
    kwalifikowanym i ważnym certyfikacie w sprawie, w której nikt o nich nie mówił."""
    copied = [outcome for outcome in outcomes(graph) if outcome.copied]

    assert not copied, (
        f"{graph}: z przykładu — "
        + "; ".join(f"{outcome.case.label}: {outcome.assessment}" for outcome in copied)
    )


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_no_marker_is_malformed(graph: str, outcomes: HandoffOutcomesOf) -> None:
    """Sprawdza, czy każdy napis w klamrach w wiadomości to znacznik anonimizacji albo placeholder
    z promptu, bez odmiany.

    Wyłapuje odmieniony znacznik („{IMIENIA}”) i wymyślony placeholder („{KOD_BŁĘDU}”):
    wdrożeniowiec nie wie, co w tym miejscu uzupełnić, bo takiej danej nikt nie ustalił."""
    broken = [outcome for outcome in outcomes(graph) if outcome.malformed]

    assert not broken, (
        f"{graph}: znaczniki — "
        + ", ".join(f"{outcome.case.case_id}: {outcome.assessment}" for outcome in broken)
    )
