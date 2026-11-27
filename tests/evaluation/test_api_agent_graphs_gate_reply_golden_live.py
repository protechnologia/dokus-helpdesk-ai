"""
Description:
Pomiar bramki wysyłki na prawdziwych wiadomościach z korpusu instancji (p. 33.3): fałszywe alarmy
i przepuszczenia na 179 wiadomościach konsultantów z zestawu
`data/unsafe/golden/graph-gate-reply.json`. Wejście bramki to treść komentarza konsultanta
wycięta z wątku z `corpus/anonymized/`, czyli to, co konsultant wysłał klientowi; werdykt
porównuje się z regułami, które według oceniających wiadomość łamie.

| test (`test_…`)                          | co liczy                      | próg               |
|------------------------------------------|-------------------------------|--------------------|
| `every_message_gets_an_accepted_verdict` | wiadomości bez werdyktu       | 0                  |
| `false_alarms_stay_within_the_threshold` | blokady wiadomości poprawnych | `MAX_FALSE_ALARMS` |
| `misses_stay_within_the_threshold`       | przepuszczenia na regułę      | `MAX_MISSES`       |
| `no_marker_is_malformed`                 | znaczniki przekręcone         | 0                  |

Przepuszczenia liczy się osobno na każdą regułę: wiadomość łamiąca dwie reguły, którą bramka
przepuściła, liczy się przy obu. Czy bramka zablokowała z właściwego powodu, test nie sprawdza,
bo werdykt nie podaje numeru reguły; mówi o tym uzasadnienie w raporcie. Wpisy wątpliwe liczą się
w progach razem z resztą, a raport podaje je osobno.

Co się dzieje po drodze:

1. `measure_gate_reply_cases()` sprawdza wersję reguł i skrót każdej wiadomości, zanim zawoła
   model.
2. Wiadomości idą przez graf `gate_reply` na regułach z zestawu domyślnego, po 4 naraz, z czasem
   każdej sprawy; anonimizator to atrapa, bo wiadomości są już po anonimizacji.
3. Raport po przebiegu (fixture `gate_reply_report`) podaje liczniki razem, przepuszczenia na
   regułę, liczniki dla wpisów wątpliwych i na warstwę, czas bramki z doliczoną anonimizacją i pod
   każdym złym werdyktem łamane reguły z powodem i uzasadnienie modelu.

Pomiary (`gpt-6.1-sol`, dwa przebiegi, 2026-11-25):

| reguły | fałszywe alarmy | przepuszczenia | reguła 2 | reguła 5    | reguły 1, 3, 4, 6 |
|--------|-----------------|----------------|----------|-------------|-------------------|
| v3     | 16 i 18 ze 108  | 12 i 11 z 71   | 2 z 5    | 10 i 9 z 58 | 0 z 24            |
| v4     | 9 i 8 ze 108    | 2 i 2 z 71     | 0 z 5    | 2 z 58      | 0 z 24            |

Na regułach w wersji 3 wszystkie złe werdykty stały na granicach, które człowiek ustalił inaczej,
niż mówiło brzmienie reguł: bramka brała za potoczny żargon helpdesku, a przepuszczała swobodne
zwroty, blokowała „pani” małą literą o osobie trzeciej i nie uznawała za błąd błędnej formy
wyrazu. Wersja 4 zapisuje te granice. Zostają alarmy przy „poszło”, przy radzie spakowania plików
do ZIP i przy formach, które bramka uznaje za błędne („PIN” bez końcówki), a wiadomości
bezosobowe („proszę sprawdzić”) bramka blokowała za brak formy „Pan”, „Pani” albo „Państwo”.
Zdanie o formie bezosobowej doszło do reguły 3 po pomiarze i nie jest zmierzone.

O czym pamiętać przy zmianach:

- Próg to gorszy wynik z dwóch przebiegów na tym samym modelu: model nie jest deterministyczny
  przy temperaturze 0. Zmiana promptu bramki albo reguł to ten pomiar od nowa, dwa przebiegi.
- Czasu test nie sprawdza, tylko go podaje: cierpliwość UI helpdesku ustala wpięcie (p. 38).
- Zestaw i korpus to dane klientów, poza repo: bez nich testy się pomija. Raport cytuje
  uzasadnienia modelu, a trzy wiadomości reguły 6 niosą hasła z korpusu, więc wydruk zostaje na
  ekranie, a do CLAUDE.md idą same liczby.
- KOSZTUJE: sprawa to jedna tura modelu na krótkiej wiadomości. Cały zestaw na `gpt-6.1-sol`
  i regułach w wersji 4 to 0,87 USD przy pierwszym przebiegu po zmianie reguł albo promptu
  i 0,28 USD przy kolejnym, z początkiem żądania z cache, oraz około 3 minut.
"""

import pytest

from tests._helpers.golden_gate_reply import (
    ANONYMIZED_DIR,
    GOLDEN_FILE,
    MAX_FALSE_ALARMS,
    MAX_MISSES,
    RULES,
    GateReplyOutcome,
    GateReplyReport,
    golden_gate_reply_cases,
    measure_gate_reply_cases,
)
from tests._helpers.live import LiveUsageReport, live_generation_llm

pytestmark = [
    pytest.mark.llm_live,
    pytest.mark.skipif(
        not GOLDEN_FILE.is_file() or not ANONYMIZED_DIR.is_dir(),
        reason="zestawu bramki wysyłki i wątków korpusu nie ma w repo",
    ),
]


@pytest.fixture(scope="module")
def outcomes(
    request:           pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    live_usage:        LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia
    gate_reply_report: GateReplyReport,        # wstrzykiwane przez pytest; raport ocen wiadomości
) -> list[GateReplyOutcome]:
    """
    Description:
    Przeprowadza wszystkie wiadomości zestawu przez bramkę na żywym modelu i oddaje ich oceny.
    Liczy się raz na plik: wszystkie testy dostają te same oceny, a błąd pomiaru pytest
    zapamiętuje i zgłasza każdemu testowi bez ponownego wołania modelu.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        [GateReplyOutcome(case=GoldenGateReplyCase(ticket_id="23921", …), answer="block", …), …]
    """
    llm = live_generation_llm(request.config)

    return measure_gate_reply_cases(golden_gate_reply_cases(), llm, live_usage, gate_reply_report)


def test_every_message_gets_an_accepted_verdict(outcomes: list[GateReplyOutcome]) -> None:
    """Sprawdza, czy każda wiadomość z zestawu kończy się werdyktem, który węzeł odpowiedzi
    przyjął.

    Wyłapuje wiadomość, na której model nie umie oddać werdyktu w kształcie narzędzia
    odpowiedzi nawet po poprawce, na przykład bardzo krótką albo z wklejonym logiem: helpdesk
    dostaje wtedy 503 i wysyła bez bramki."""
    rejected = [outcome.case.label for outcome in outcomes if outcome.rejected]

    assert not rejected, f"bez werdyktu: {', '.join(rejected)}"


def test_false_alarms_stay_within_the_threshold(outcomes: list[GateReplyOutcome]) -> None:
    """Sprawdza, czy bramka blokuje najwyżej `MAX_FALSE_ALARMS` wiadomości z tych, które według
    etykiet nie łamią żadnej reguły.

    Wyłapuje bramkę, która blokuje poprawne wiadomości, na przykład za nazwę przycisku w
    cytacie, za żargon helpdesku albo za znacznik anonimizacji w miejscu danej: fałszywy alarm
    uczy wdrożeniowców klikać furtkę odruchowo, a wtedy bramka nie działa już wcale."""
    alarms = [outcome.case.label for outcome in outcomes if outcome.false_alarm]

    assert len(alarms) <= MAX_FALSE_ALARMS, (
        f"fałszywych alarmów {len(alarms)} przy progu {MAX_FALSE_ALARMS}: {', '.join(alarms)}"
    )


@pytest.mark.parametrize("rule", RULES)
def test_misses_stay_within_the_threshold(
    rule:     int,                     # np. 5
    outcomes: list[GateReplyOutcome],  # wstrzykiwane przez pytest; oceny wiadomości
) -> None:
    """Sprawdza, czy wśród wiadomości łamiących daną regułę bramka przepuszcza najwyżej tyle,
    ile pozwala `MAX_MISSES` dla tej reguły.

    Wyłapuje bramkę, która przepuszcza wiadomość z hasłem w treści, z prośbą o token albo
    o hasło, z błędem ortograficznym albo ze zwrotem do klienta małą literą: do klienta wychodzi
    wtedy dokładnie to, czego reguła klienta zabrania."""
    misses = [
        outcome.case.label
        for outcome in outcomes
        if rule in outcome.case.broken_rules and outcome.miss
    ]

    assert len(misses) <= MAX_MISSES[rule], (
        f"reguła {rule}: przepuszczeń {len(misses)} przy progu {MAX_MISSES[rule]}: "
        + ", ".join(misses)
    )


def test_no_marker_is_malformed(outcomes: list[GateReplyOutcome]) -> None:
    """Sprawdza, czy w uzasadnieniu i wskazówce każdego werdyktu napisy w klamrach są
    znacznikami anonimizacji albo placeholderami z promptu, bez odmiany i bez zmiany liter.

    Wyłapuje werdykt, w którym model odmienił znacznik z wiadomości („{NAZWISKA}”) albo wymyślił
    własny: wdrożeniowiec nie wie wtedy, o którą daną chodzi, a anonimizacja przestaje być
    widoczna."""
    malformed = [
        f"{outcome.case.label}: {outcome.malformed}" for outcome in outcomes if outcome.malformed
    ]

    assert not malformed, f"przekręcone znaczniki — {', '.join(malformed)}"
