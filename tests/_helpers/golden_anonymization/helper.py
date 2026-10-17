"""
Description:
Golden set anonimizatora (p. 19.3) i ocena tekstu po anonimizacji: co z danych, które miały
zniknąć, zostało w wyniku, i czego z wiedzy, która miała zostać, w wyniku ubyło. Przypadek to
tekst z dwiema listami fragmentów: `remove` (dane z rodzajem) i `keep` (wiedza z rodzajem);
czego nie ma na żadnej liście, ocena nie sprawdza. Zestawy są dwa: zmyślony
(`data/safe/golden/anonymization.json`) i próbka korpusu (`data/unsafe/golden/anonymization.json`).

| co                          | do czego                                                       |
|-----------------------------|----------------------------------------------------------------|
| `anonymization_set()`       | wczytanie jednego zestawu                                      |
| `words()`                   | słowa tekstu do porównań                                       |
| `judge_anonymization()`     | ocena wyniku jednego przypadku                                 |
| `measure_anonymization()`   | ocena całego zestawu przez podaną funkcję i liczniki na rodzaj |
| `annotation_problems()`     | kontrola samego zestawu: czy zaznaczenia pasują do tekstu      |
| `replace_marked()`          | tekst z zaznaczonymi danymi zamienionymi na znaczniki          |
| `ideal_anonymizer()`        | anonimizator, który robi dokładnie `replace_marked()`          |

Przykład — tekst „Jan Nowak <jan.nowak@ug.pl>, tel. 600 123 456”, w `remove` IMIĘ „Jan”,
NAZWISKO „Nowak”, EMAIL „jan.nowak@ug.pl” i TELEFON „600 123 456”:

    wynik „{IMIĘ} {NAZWISKO} <{EMAIL}>, tel. {TELEFON} 456”
        -> przecieki: TELEFON „600 123 456”      (słowo „456” zostało)
    wynik „{IMIĘ} {NAZWISKO} <jan.nowak@ug.pl>, tel. {TELEFON}”
        -> przecieki: EMAIL „jan.nowak@ug.pl”    (imię i nazwisko w adresie należą do adresu)

Jak przypadek jest oceniany:

1. Tekst wejściowy i wynik dzielą się na słowa: ciągi liter i cyfr, bez wielkości liter
   i polskich znaków. Fragment stoi w tekście, gdy jego słowa stoją tam kolejno, więc
   interpunkcja i podział linii nie mają znaczenia.
2. Każde wystąpienie fragmentu z `remove` w wejściu jest zaznaczone. Wystąpienie wewnątrz
   dłuższego fragmentu (imię w adresie e-mail) należy do dłuższego.
3. Fragment wycieka, gdy stoi w wyniku w całości albo gdy któreś jego słowo stoi w wyniku
   częściej, niż stało w wejściu poza zaznaczeniami. To drugie łapie przeciek częściowy
   („{TELEFON} 456”).
4. Wiedza jest zniszczona, gdy fragment z `keep` stoi w wyniku rzadziej niż w wejściu.

O czym pamiętać przy zmianach:

- Przy próbce korpusu ocena i komunikaty nazywają fragment rodzajem z numerem, nigdy treścią:
  komunikat trafia do konsoli, a fragment jest daną klienta.
- Słowa fragmentu z `remove` w każdym miejscu tekstu muszą być daną. Pułapkę z tym samym
  słowem w zwykłym znaczeniu pisze się inną formą („Pani Mróz” obok „przez mrozy”).
- Fragment z `remove` to sama dana, bez etykiety („600 123 456”, nie „tel. 600 123 456”):
  etykieta zostaje w tekście, a słowo z niej liczyłoby się jako przeciek.
"""

import json
import unicodedata
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tests._helpers.golden_anonymization.constants import (
    EXTRA_LETTERS,
    KEEP_KINDS,
    REMOVE_KINDS,
    WORD,
)
from tests._helpers.golden_anonymization.models.anonymization_case import AnonymizationCase
from tests._helpers.golden_anonymization.models.anonymization_measurement import (
    AnonymizationMeasurement,
)
from tests._helpers.golden_anonymization.models.anonymization_outcome import AnonymizationOutcome
from tests._helpers.golden_anonymization.models.anonymization_set import AnonymizationSet
from tests._helpers.golden_anonymization.models.fragment import Fragment
from tests._helpers.golden_anonymization.models.kind_count import KindCount

# Funkcja anonimizująca jeden tekst: metoda silnika w procesie albo klienta usługi.
Anonymize = Callable[[str], Awaitable[str]]

# Wystąpienie fragmentu w tekście: od którego słowa do którego (bez ostatniego).
Span = tuple[int, int]


def anonymization_set(
    path: Path,  # np. Path("data/safe/golden/anonymization.json")
) -> AnonymizationSet:
    """
    Description:
    Wczytuje jeden zestaw golden setu anonimizatora. `synthetic` pochodzi z metryczki zestawu
    i nie ma wartości domyślnej, jak w paczce dokumentacji: od niego zależy, czy ocena pokazuje
    fragmenty.

    Example args:
        path=Path("data/safe/golden/anonymization.json")

    Example result:
        AnonymizationSet(name="anonymization-v1", synthetic=True,
                         cases=(AnonymizationCase(case_id="s01", …), …))
    """
    raw       = json.loads(path.read_text(encoding="utf-8"))
    synthetic = raw["meta"]["synthetic"]

    golden = AnonymizationSet(
        name      = raw["meta"]["name"],
        synthetic = synthetic,
        cases     = tuple(_case_from(entry, synthetic) for entry in raw["cases"]),
    )

    return golden


def _case_from(
    entry:     Mapping[str, Any],  # np. {"id": "s01", "text": "…", "remove": {"IMIĘ": ["Jan"]}}
    synthetic: bool,               # np. True
) -> AnonymizationCase:
    """
    Description:
    Zamienia wpis przypadku z zestawu na `AnonymizationCase`. Listy fragmentów stoją w zestawie
    po rodzaju, więc rodzaj pisze się raz na kilka fragmentów.

    Example args:
        entry={"id": "s01", "phenomenon": "…", "text": "Jan Nowak…",
               "remove": {"IMIĘ": ["Jan"], "NAZWISKO": ["Nowak"]}, "keep": {}}
        synthetic=True

    Example result:
        AnonymizationCase(case_id="s01", remove=(Fragment(kind="IMIĘ", text="Jan", number=1),
                          …), keep=(), synthetic=True, ticket_id=None, …)
    """
    case = AnonymizationCase(
        case_id    = entry["id"],
        phenomenon = entry["phenomenon"],
        text       = entry["text"],
        remove     = _fragments_from(entry["remove"]),
        keep       = _fragments_from(entry["keep"]),
        synthetic  = synthetic,
        ticket_id  = entry.get("ticket_id"),
    )

    return case


def _fragments_from(
    by_kind: Mapping[str, Sequence[str]],  # np. {"IMIĘ": ["Jan", "Anna"], "NAZWISKO": ["Nowak"]}
) -> tuple[Fragment, ...]:
    """
    Description:
    Rozwija fragmenty zapisane po rodzaju na płaską listę z numerem fragmentu w jego rodzaju.
    Rodzaju nie sprawdza: nieznany rodzaj zgłasza `annotation_problems()`, z nazwą przypadku.

    Example args:
        by_kind={"IMIĘ": ["Jan", "Anna"], "NAZWISKO": ["Nowak"]}

    Example result:
        (Fragment(kind="IMIĘ", text="Jan", number=1), Fragment(kind="IMIĘ", text="Anna",
         number=2), Fragment(kind="NAZWISKO", text="Nowak", number=1))
    """
    fragments = tuple(
        Fragment(kind=kind, text=text, number=number)
        for kind, texts in by_kind.items()
        for number, text in enumerate(texts, start=1)
    )

    return fragments


def words(
    text: str,  # np. "Pani Annie Wiśniewskiej,\ntel. 600-123-456"
) -> tuple[str, ...]:
    """
    Description:
    Dzieli tekst na słowa do porównań: ciągi liter i cyfr, małymi literami i bez polskich znaków.
    Silnik, który zmieni wielkość liter albo zgubi ogonek, nadal zostawia daną.

    Example args:
        text="Pani Annie Wiśniewskiej,\\ntel. 600-123-456"

    Example result:
        ("pani", "annie", "wisniewskiej", "tel", "600", "123", "456")
    """
    return tuple(_fold(match.group()) for match in WORD.finditer(text))


def _fold(
    word: str,  # np. "Wiśniewskiej"
) -> str:
    """
    Description:
    Zapisuje jedno słowo do porównań: małe litery, bez polskich znaków (także „ł”).

    Example args:
        word="Wiśniewskiej"

    Example result:
        "wisniewskiej"
    """
    folded  = word.casefold().translate(EXTRA_LETTERS)
    letters = unicodedata.normalize("NFKD", folded)

    return "".join(char for char in letters if not unicodedata.combining(char))


def judge_anonymization(
    case:   AnonymizationCase,  # np. przypadek z zestawu zmyślonego
    output: str,                # tekst po anonimizacji, np. "{IMIĘ} {NAZWISKO} <{EMAIL}>…"
) -> AnonymizationOutcome:
    """
    Description:
    Ocenia wynik anonimizacji jednego przypadku: które dane zostały w wyniku choćby częścią
    i której wiedzy ubyło. Kroki oceny opisuje docstring modułu.

    Example args:
        case=AnonymizationCase(case_id="s01", text="Jan Nowak, tel. 600 123 456", …)
        output="{IMIĘ} {NAZWISKO}, tel. {TELEFON} 456"

    Example result:
        AnonymizationOutcome(leaked=(Fragment(kind="TELEFON", text="600 123 456", …),),
                             destroyed=(), …)
    """
    source = words(case.text)
    result = words(output)

    # --- dane: w całości albo słowem ponad to, co stało poza zaznaczeniami ---
    left_free = Counter(_unmarked(source, case.remove))
    left_out  = Counter(_unmarked(result, case.remove))
    surplus   = left_out - left_free
    whole     = _owned(case.remove, result)

    leaked = tuple(
        fragment
        for fragment, spans in zip(case.remove, whole, strict=True)
        if spans or any(surplus[word] for word in words(fragment.text))
    )

    # --- wiedza: fragment stoi w wyniku rzadziej niż w wejściu ---
    destroyed = tuple(
        fragment
        for fragment in case.keep
        if len(_occurrences(fragment, result)) < len(_occurrences(fragment, source))
    )

    outcome = AnonymizationOutcome(case=case, leaked=leaked, destroyed=destroyed)

    return outcome


def _unmarked(
    text_words: Sequence[str],       # np. ("jan", "nowak", "tel", "600", "123", "456")
    fragments:  Sequence[Fragment],  # np. (Fragment(kind="TELEFON", text="600 123 456", …),)
) -> list[str]:
    """
    Description:
    Słowa tekstu, które nie należą do żadnego wystąpienia podanych fragmentów.

    Example args:
        text_words=("jan", "nowak", "tel", "600", "123", "456")
        fragments=(Fragment(kind="TELEFON", text="600 123 456", number=1),)

    Example result:
        ["jan", "nowak", "tel"]
    """
    marked = {
        index
        for spans in _owned(fragments, text_words)
        for start, end in spans
        for index in range(start, end)
    }

    return [word for index, word in enumerate(text_words) if index not in marked]


def _occurrences(
    fragment:   Fragment,       # np. Fragment(kind="IMIĘ", text="Jan", number=1)
    text_words: Sequence[str],  # np. ("jan", "nowak", "jan", "nowak", "ug", "pl")
) -> list[Span]:
    """
    Description:
    Wszystkie wystąpienia fragmentu w tekście: miejsca, w których jego słowa stoją kolejno.

    Example args:
        fragment=Fragment(kind="IMIĘ", text="Jan", number=1)
        text_words=("jan", "nowak", "jan", "nowak", "ug", "pl")

    Example result:
        [(0, 1), (2, 3)]
    """
    needle = words(fragment.text)
    size   = len(needle)

    # Fragment bez słów nie stoi nigdzie; zgłasza go `annotation_problems()`.
    if not size:
        return []

    spans = [
        (start, start + size)
        for start in range(len(text_words) - size + 1)
        if tuple(text_words[start:start + size]) == needle
    ]

    return spans


def _owned(
    fragments:  Sequence[Fragment],  # np. IMIĘ „Jan” i EMAIL „jan.nowak@ug.pl”
    text_words: Sequence[str],       # np. ("jan", "nowak", "jan", "nowak", "ug", "pl")
) -> list[list[Span]]:
    """
    Description:
    Wystąpienia każdego fragmentu, bez tych, które leżą wewnątrz dłuższego wystąpienia innego
    fragmentu: imię w adresie e-mail należy do adresu. Lista na fragment, w kolejności fragmentów.

    Example args:
        fragments=(Fragment(kind="IMIĘ", text="Jan", number=1),
                   Fragment(kind="EMAIL", text="jan.nowak@ug.pl", number=1))
        text_words=("jan", "nowak", "jan", "nowak", "ug", "pl")

    Example result:
        [[(0, 1)], [(2, 6)]]
    """
    found = [_occurrences(fragment, text_words) for fragment in fragments]
    every = [span for spans in found for span in spans]

    owned = [
        [span for span in spans if not any(_inside(span, other) for other in every)]
        for spans in found
    ]

    return owned


def _inside(
    span:  Span,  # np. (2, 3)
    other: Span,  # np. (2, 6)
) -> bool:
    """
    Description:
    Mówi, czy wystąpienie leży wewnątrz innego, dłuższego wystąpienia.

    Example args:
        span=(2, 3)
        other=(2, 6)

    Example result:
        True
    """
    return other[0] <= span[0] and span[1] <= other[1] and other[1] - other[0] > span[1] - span[0]


async def measure_anonymization(
    golden:    AnonymizationSet,  # np. anonymization_set(SAFE_FILE)
    anonymize: Anonymize,         # np. FakeEngine().anonymize
) -> AnonymizationMeasurement:
    """
    Description:
    Anonimizuje każdy tekst zestawu podaną funkcją, ocenia wyniki i liczy przecieki oraz
    zniszczoną wiedzę osobno na każdy rodzaj, który w zestawie stoi. Jednostką licznika jest
    fragment z listy przypadku, nie jego wystąpienie.

    Example args:
        golden=anonymization_set(SAFE_FILE)
        anonymize=FakeEngine().anonymize

    Example result:
        AnonymizationMeasurement(outcomes=(…), leaks={"IMIĘ": KindCount(found=24, total=24), …},
                                 destroyed={"KOD_BŁĘDU": KindCount(found=0, total=9), …})
    """
    outcomes = []

    # Po kolei: usługa dostaje wtedy jedno żądanie naraz, jak przy zwykłej pracy.
    for case in golden.cases:
        outcomes.append(judge_anonymization(case, await anonymize(case.text)))

    pairs   = list(zip(golden.cases, outcomes, strict=True))
    removed = [(case.remove, outcome.leaked) for case, outcome in pairs]
    kept    = [(case.keep, outcome.destroyed) for case, outcome in pairs]

    measurement = AnonymizationMeasurement(
        outcomes  = tuple(outcomes),
        leaks     = _count_by_kind(REMOVE_KINDS, removed),
        destroyed = _count_by_kind(KEEP_KINDS, kept),
    )

    return measurement


def _count_by_kind(
    kinds:  Sequence[str],                                           # np. REMOVE_KINDS
    judged: Sequence[tuple[Sequence[Fragment], Sequence[Fragment]]],  # (zaznaczone, złe)
) -> dict[str, KindCount]:
    """
    Description:
    Liczy na rodzaj, ile fragmentów poszło źle i ile ich było. Rodzaj, którego w zestawie nie
    ma, w wyniku nie stoi: licznik „0 z 0” wyglądałby jak rodzaj zmierzony bez błędu.

    Example args:
        kinds=("IMIĘ", "PESEL")
        judged=[((Fragment(kind="IMIĘ", …), Fragment(kind="IMIĘ", …)),
                 (Fragment(kind="IMIĘ", …),))]

    Example result:
        {"IMIĘ": KindCount(found=1, total=2)}
    """
    totals = Counter(fragment.kind for marked, _ in judged for fragment in marked)
    wrong  = Counter(fragment.kind for _, found in judged for fragment in found)

    counts = {
        kind: KindCount(found=wrong[kind], total=totals[kind])
        for kind in kinds
        if totals[kind]
    }

    return counts


def annotation_problems(
    case: AnonymizationCase,  # np. przypadek z próbki korpusu
) -> tuple[str, ...]:
    """
    Description:
    Sprawdza sam zestaw, nie anonimizator: czy listy `remove` i `keep` przypadku, pisane
    ręcznie, pasują do jego tekstu. Woła ją test spójności zestawu, zanim zestaw posłuży do
    pomiaru, i oddaje listę problemów; pusta lista znaczy, że przypadek jest dobrze zaznaczony.

    Po co: pomyłka w zaznaczeniach nie daje błędu, tylko fałszywy wynik pomiaru.

    | problem                                  | czym grozi                                  |
    |------------------------------------------|---------------------------------------------|
    | rodzaj spoza listy                       | licznik rodzaju pod literówką               |
    | fragment bez słów                        | fragment, który nigdzie nie stoi            |
    | ten sam fragment dwa razy                | podwójny licznik; w obu listach naraz —     |
    |                                          | dana, która ma zarazem zniknąć i zostać     |
    | dana, której nie ma w tekście            | dana, która nigdy nie wycieknie             |
    | dana tylko wewnątrz innej (imię jedynie  | wpis bez skutku: wystąpienie należy do      |
    | w adresie e-mail)                        | dłuższego fragmentu                         |
    | dwie dane zachodzące na siebie częściowo | wzorcowa zamiana nie ma jak ich wyciąć      |
    | wiedza, której nie ma w tekście          | wiedza, której nie da się zniszczyć         |
    | wiedza zachodząca na daną                | fragment, który ma zarazem zniknąć i zostać |

    Komunikaty nazywają fragment jak ocena: przy próbce korpusu rodzajem z numerem, bez treści.

    Example args:
        case=AnonymizationCase(case_id="s01", text="Jan Nowak", remove=(Fragment(kind="IMIĘ",
                               text="Anna", number=1),), …)

    Example result:
        ("IMIĘ „Anna”: nie stoi w tekście",)
    """
    text_words = words(case.text)
    owned      = _owned(case.remove, text_words)
    problems   = []

    # --- rodzaje z list i fragmenty, które mają słowa ---
    for fragments, kinds in ((case.remove, REMOVE_KINDS), (case.keep, KEEP_KINDS)):
        for fragment in fragments:
            name = fragment.shown(case.synthetic)

            if fragment.kind not in kinds:
                problems.append(f"{name}: rodzaj spoza listy")

            if not words(fragment.text):
                problems.append(f"{name}: fragment bez słów")

    # --- ten sam fragment dwa razy, także raz w każdej liście ---
    seen: dict[tuple[str, ...], Fragment] = {}

    for fragment in (*case.remove, *case.keep):
        key = words(fragment.text)

        if key in seen:
            problems.append(
                f"{fragment.shown(case.synthetic)}: powtarza {seen[key].shown(case.synthetic)}"
            )

        seen.setdefault(key, fragment)

    # --- dane: stoją w tekście, i to nie tylko wewnątrz innego fragmentu ---
    for fragment, spans in zip(case.remove, owned, strict=True):
        name = fragment.shown(case.synthetic)

        if not _occurrences(fragment, text_words):
            problems.append(f"{name}: nie stoi w tekście")
        elif not spans:
            problems.append(f"{name}: stoi tylko wewnątrz innego fragmentu")

    # --- wystąpienia danych nie zachodzą na siebie częściowo ---
    every = [(fragment, span) for fragment, spans in zip(case.remove, owned, strict=True)
             for span in spans]

    for index, (fragment, span) in enumerate(every):
        for other, other_span in every[index + 1:]:
            if span[0] < other_span[1] and other_span[0] < span[1]:
                problems.append(
                    f"{fragment.shown(case.synthetic)}: zachodzi na "
                    f"{other.shown(case.synthetic)}"
                )

    # --- wiedza: stoi w tekście i nie zachodzi na żadną daną ---
    marked = {index for _, span in every for index in range(*span)}

    for fragment in case.keep:
        name  = fragment.shown(case.synthetic)
        spans = _occurrences(fragment, text_words)

        if not spans:
            problems.append(f"{name}: nie stoi w tekście")
        elif any(index in marked for span in spans for index in range(*span)):
            problems.append(f"{name}: zachodzi na daną z listy remove")

    return tuple(problems)


def replace_marked(
    case: AnonymizationCase,  # np. przypadek „Jan Nowak <jan.nowak@ug.pl>”
) -> str:
    """
    Description:
    Zamienia każde zaznaczone wystąpienie danej na znacznik jej rodzaju i nie rusza niczego
    więcej. To wzór anonimizacji, którą zestaw przewiduje: ocena takiego wyniku ma wyjść bez
    przecieków i bez zniszczonej wiedzy, inaczej błędne są zaznaczenia.

    Example args:
        case=AnonymizationCase(text="Jan Nowak <jan.nowak@ug.pl>", remove=(IMIĘ „Jan”,
                               NAZWISKO „Nowak”, EMAIL „jan.nowak@ug.pl”), …)

    Example result:
        "{IMIĘ} {NAZWISKO} <{EMAIL}>"
    """
    matches = list(WORD.finditer(case.text))
    owned   = _owned(case.remove, [_fold(match.group()) for match in matches])

    # Od końca tekstu, żeby zamiana nie przesuwała miejsc, które czekają na swoją kolej.
    cuts = sorted(
        (
            (matches[start].start(), matches[end - 1].end(), fragment.kind)
            for fragment, spans in zip(case.remove, owned, strict=True)
            for start, end in spans
        ),
        reverse=True,
    )

    text = case.text

    for start, end, kind in cuts:
        text = f"{text[:start]}{{{kind}}}{text[end:]}"

    return text


def ideal_anonymizer(
    golden: AnonymizationSet,  # np. anonymization_set(SAFE_FILE)
) -> Anonymize:
    """
    Description:
    Anonimizator, który każdemu tekstowi zestawu oddaje `replace_marked()`. Służy sprawdzeniu
    samego zestawu: pomiar nim ma wyjść bez przecieków i bez zniszczonej wiedzy.

    Example args:
        golden=anonymization_set(SAFE_FILE)

    Example result:
        funkcja async: "Jan Nowak <jan.nowak@ug.pl>" -> "{IMIĘ} {NAZWISKO} <{EMAIL}>"
    """
    replaced = {case.text: replace_marked(case) for case in golden.cases}

    async def anonymize(
        text: str,  # np. "Jan Nowak <jan.nowak@ug.pl>"
    ) -> str:
        """
        Description:
        Oddaje wzorcowy wynik dla tekstu z zestawu.

        Example args:
            text="Jan Nowak <jan.nowak@ug.pl>"

        Example result:
            "{IMIĘ} {NAZWISKO} <{EMAIL}>"

        Raises:
            KeyError: tekstu nie ma w zestawie
        """
        return replaced[text]

    return anonymize
