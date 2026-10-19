"""
Description:
Węzeł `find_persons` grafu anonimizacji (p. 19.5): model anonimizujący wskazuje imiona
i nazwiska w tekście po wzorcach, a kod znajduje je w tekście i rozprowadza każde wskazane słowo
na wszystkie jego odmiany w całym wątku. Model tekstu nie przepisuje, więc nie może zgubić ani
zmienić wiedzy. Biegnie równolegle z węzłem adresów, na tych samych częściach tekstu.

Przykład (zmyślony):

    tekst:   „Od: Bogumił Cieślak <{EMAIL}>\\nPani Bronisławo, rozmawiałem z p. Cieślakiem.”
    model:   Bogumił (IMIĘ), Cieślak (NAZWISKO), Bronisławo (IMIĘ)
    miejsca: „Bogumił”, „Cieślak”, „Bronisławo”, „Cieślakiem”
    po:      „Od: {IMIĘ} {NAZWISKO} <{EMAIL}>\\nPani {IMIĘ}, rozmawiałem z p. {NAZWISKO}.”

Kroki:

1. Model wskazuje fragmenty w każdej części tekstu (`ask_model()`): słowo po słowie, w formie
   z tekstu, z rodzajem IMIĘ albo NAZWISKO.
2. Każdy fragment szuka się w całym tekście dosłownie, na granicy słów, poza znacznikami.
3. Każde słowo fragmentu, poza zwrotami i rolami, rozprowadza się na wszystkie jego odmiany
   w całym tekście (`find_word_forms()`). Tak znika osoba, którą model podał w mianowniku albo
   wskazał w jednym miejscu, a stoi w kilku.
4. Odpadają miejsca w liniach etykiet wątku i miejsca, które same są zwrotem albo rolą.

O czym pamiętać przy zmianach:

- Bez rozprowadzenia sonda z 2026-10-17 przepuszczała 4 imiona z 49; z nim — żadnego.
- Ten sam znacznik nie znaczy tej samej osoby: odmian nikt nie grupuje (CLAUDE.md -> „Świadomie
  pominięte”).
- Etykiety wątku (`LABEL_LINE`) to format `RawTicket.as_thread()` w `api`: rola i data, bez
  nazwisk. Zmiana tego formatu w `api` wymaga zmiany wyrażenia tutaj.
"""

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from anonymizer_app.agent_nodes.ask_model import ask_model
from anonymizer_app.agent_nodes.base import Node
from anonymizer_app.core_errors.llm_error import LLMError
from anonymizer_app.core_model.found import Found
from anonymizer_app.core_service.finder_markers import marker_spans
from anonymizer_app.core_service.finder_word_forms import (
    LETTERS,
    MIN_WORD_LETTERS,
    find_word_forms,
    is_stem_form,
)
from anonymizer_app.core_util.fold import fold_word
from anonymizer_app.core_util.spans import is_inside
from anonymizer_app.engine_llm import LLMClient

# Katalog promptu węzła: `prompt_system.md` i `examples.json` leżą obok tego pliku.
PROMPT_DIR = Path(__file__).parent

# Rodzaje, które model może wskazać; zarazem nazwy znaczników.
PERSON_KINDS = ("IMIĘ", "NAZWISKO")

# Schemat odpowiedzi: serwer dekoduje tylko tokeny, które go spełniają, więc rodzaj spoza listy
# nie może się pojawić. Klucze po polsku, jak w prompcie, z którym je mierzono.
SCHEMA_NAME = "osoby"
ITEMS_KEY   = "dane"
SCHEMA      = {
    "type":       "object",
    "properties": {
        ITEMS_KEY: {
            "type":  "array",
            "items": {
                "type":       "object",
                "properties": {
                    "tekst":  {"type": "string"},
                    "rodzaj": {"enum": list(PERSON_KINDS)},
                },
                "required":   ["tekst", "rodzaj"],
            },
        },
    },
    "required":   [ITEMS_KEY],
}

# Limit odpowiedzi na część tekstu. Element to około 15 tokenów, więc limit mieści ponad 90 form
# w jednej części; zapętlonej odpowiedzi nie pozwala ciągnąć się dłużej niż kilkanaście sekund.
MAX_ANSWER_TOKENS = 1500

# Zwroty i role, złożone przez `fold_word()`: ich węzeł nie zamienia, nawet gdy model je wskazał
# albo gdy wyglądają na odmianę wskazanego słowa. Etykiety komentarzy niosą role („klient”,
# „konsultant”), a zwrot stoi przed każdym nazwiskiem w korespondencji.
NOT_NAMES = frozenset({
    "pan",
    "pani",
    "pana",
    "panu",
    "panem",
    "pania",
    "panie",
    "panstwo",
    "panstwa",
    "panstwu",
    "klient",
    "konsultant",
    "kierownik",
    "urzad",
    "platforma",
})

# Plik z nazwami aplikacji, skrzynek i systemów tej instalacji, które nie są osobami — obok
# promptu. Lista trafia do promptu (`{{exceptions}}`) i do filtra w kodzie: słowa z niej
# i ich odmian węzeł nie zamienia, nawet gdy model je wskaże. W jednym wątku próbki korpusu model
# brał nazwę skrzynki „dokus” za nazwisko, a jej odmiany niszczyły nazwę aplikacji w całym wątku.
EXCEPTIONS_FILE = "exceptions.json"

# Linie etykiet wątku z `RawTicket.as_thread()` w `api`: sama metryka, osoby w nich nie stoją.
LABEL_LINE = re.compile(r"^(KOMENTARZ \d+ — .*|OPIS ZGŁASZAJĄCEGO:|ZGŁOSZENIE \d+ z .*)$", re.M)


class FindPersonsNode(Node):
    """
    Description:
    Węzeł grafu, który pyta model o imiona i nazwiska i zamienia jego odpowiedź na miejsca w całym
    tekście; przebieg opisuje docstring modułu. Miejsca mogą na siebie zachodzić — wybiera z nich
    węzeł `replace_found`.
    """

    name = "find_persons"

    def __init__(
        self,
        llm: LLMClient,  # np. LLMClient(base_url="https://…/v1", model="speakleash/…")
    ):
        """
        Description:
        Buduje węzeł na kliencie modelu anonimizującego.

        Example args:
            llm=LLMClient(base_url="https://…/v1", model="speakleash/…")

        Example result:
            FindPersonsNode gotowy do `run()`
        """
        self._llm = llm

    async def run(
        self,
        state: BaseModel,  # np. AnonymizeState(after_patterns="Od: Bogumił Cieślak…", chunks=[…])
    ) -> dict[str, Any]:
        """
        Description:
        Pyta model o każdą część tekstu, a miejsca wskazanych osób w `after_patterns` zapisuje
        w `persons`; w logu liczba fragmentów od modelu i liczba miejsc.

        Example args:
            state=AnonymizeState(after_patterns="Od: Bogumił Cieślak <{EMAIL}>…",
                                 chunks=["Od: Bogumił Cieślak <{EMAIL}>…"])

        Example result:
            {"persons": [Found(kind="IMIĘ", start=4, end=11), …],
             "log": [LogEntry(node="find_persons", message="2 fragmentów → 2 miejsc")]}

        Raises:
            EngineConfigError: serwer modelu odrzucił klucz albo nie zna modelu
            LLMError: model nie odpowiedział albo odpowiedział spoza schematu
        """
        exceptions = read_exceptions()
        items      = await ask_model(self._llm, PROMPT_DIR, state.chunks, SCHEMA_NAME, SCHEMA,
                                     ITEMS_KEY, MAX_ANSWER_TOKENS, prompt_values(exceptions))
        found      = place_persons(state.after_patterns, items, exceptions)

        update = {
            "persons": found,
            "log":     [self.log_entry(f"{len(items)} fragmentów → {len(found)} miejsc")],
        }

        return update


def read_exceptions() -> list[str]:
    """
    Description:
    Nazwy z `exceptions.json` obok promptu, w kolejności z pliku. Czytane przy każdym wywołaniu,
    jak prompt: poprawka w dev działa bez restartu.

    Example args:
        (brak)

    Example result:
        ["Dokus"]

    Raises:
        ValueError: plik nie jest listą niepustych napisów — błąd w danych węzła
    """
    names = json.loads((PROMPT_DIR / EXCEPTIONS_FILE).read_text(encoding="utf-8"))

    if not isinstance(names, list) or not all(isinstance(n, str) and n.strip() for n in names):
        raise ValueError(f"{EXCEPTIONS_FILE}: oczekiwana lista niepustych napisów")

    return [name.strip() for name in names]


def prompt_values(
    exceptions: Sequence[str],  # np. ["Dokus"]
) -> dict[str, str]:
    """
    Description:
    Treść miejsc w prompcie węzła: lista nazw, które nie są osobami, po jednej w linii.

    Example args:
        exceptions=["Dokus"]

    Example result:
        {"exceptions": "- Dokus"}
    """
    return {"exceptions": "\n".join(f"- {name}" for name in exceptions)}


def place_persons(
    text:       str,            # tekst po wzorcach, np. "Od: Bogumił Cieślak <{EMAIL}>…"
    items:      Sequence[Any],  # elementy odpowiedzi modelu, np. [{"tekst": "Bogumił", …}]
    exceptions: Sequence[str],  # nazwy, które nie są osobami, np. read_exceptions()
) -> list[Found]:
    """
    Description:
    Miejsca imion i nazwisk w całym tekście z elementów odpowiedzi modelu, według kroków 2–4
    z opisu modułu, każde raz. Słowo z listy nazw, które nie są osobami, i jego odmiany zostają,
    także gdy model je wskazał.

    Example args:
        text="Od: Bogumił Cieślak <{EMAIL}>\\nPani Bronisławo, rozmawiałem z p. Cieślakiem."
        items=[{"tekst": "Bogumił", "rodzaj": "IMIĘ"}, {"tekst": "Cieślak", "rodzaj": "NAZWISKO"}]
        exceptions=["Dokus"]

    Example result:
        [Found(kind="IMIĘ", start=4, end=11), Found(kind="NAZWISKO", start=12, end=19), …]

    Raises:
        LLMError: element odpowiedzi jest poza schematem
    """
    labels  = [match.span() for match in LABEL_LINE.finditer(text)]
    found   = []

    # Słowa nazw z listy, złożone; krótsze niż trzy litery („e” z „e-Doręczenia”) nie odróżniają
    # niczego, więc odpadają.
    skipped = {
        fold_word(word)
        for name in exceptions
        for word in LETTERS.findall(name)
        if len(word) >= MIN_WORD_LETTERS
    }

    for fragment, kind in _fragments(items):
        for start, end in place_person(text, fragment, skipped):
            # --- etykiety wątku, zwroty, role i nazwy, które nie są osobami, zostają ---
            if is_inside((start, end), labels) or _never_a_person(text[start:end], skipped):
                continue

            found.append(Found(kind=kind, start=start, end=end))

    # Każde miejsce raz: ta sama osoba wskazana w kilku częściach, dosłownie i jako odmiana, daje
    # te same zakresy, a log ma podawać liczbę miejsc, nie wskazań.
    return list(dict.fromkeys(found))


def place_person(
    text:     str,       # np. "Pani Bronisławo, rozmawiałem z p. Cieślakiem."
    fragment: str,       # np. "Cieślak"
    skipped:  set[str],  # nazwy, które nie są osobami, złożone, np. {"dokus"}
) -> list[tuple[int, int]]:
    """
    Description:
    Zakresy fragmentu w tekście: dosłownie, na granicy słów i poza znacznikami, a do tego
    wszystkie odmiany każdego jego słowa poza zwrotami, rolami i nazwami, które nie są osobami.
    Zakresy mogą na siebie zachodzić (fragment z dwóch słów i każde słowo osobno).

    Example args:
        text="Pan Cieślak dzwonił. Proszę oddzwonić do Cieślaka."
        fragment="Cieślak"
        skipped={"dokus"}

    Example result:
        [(4, 11), (4, 11), (41, 49)]
    """
    markers = marker_spans(text)
    literal = re.compile(rf"(?<![^\W_]){re.escape(fragment)}(?![^\W_])")
    spans   = [
        match.span()
        for match in literal.finditer(text)
        if not is_inside(match.span(), markers)
    ]

    for word in LETTERS.findall(fragment):
        if not _never_a_person(word, skipped):
            spans += find_word_forms(text, word)

    return spans


def _never_a_person(
    text:    str,       # np. "Dokusie" — słowo albo fragment z tekstu
    skipped: set[str],  # nazwy, które nie są osobami, złożone, np. {"dokus"}
) -> bool:
    """
    Description:
    Mówi, czy fragment to sam zwrot albo rola, albo czy każde jego słowo to słowo nazwy z listy,
    która nie jest osobą, lub jego odmiana po wspólnym początku (`is_stem_form()`: „Dokusie”,
    „Doręczeń”).

    Example args:
        text="Dokusie"
        skipped={"dokus"}

    Example result:
        True
    """
    if fold_word(text) in NOT_NAMES:
        return True

    words = [fold_word(word) for word in LETTERS.findall(text)]

    return bool(words) and all(
        any(word == name or is_stem_form(name, word) for name in skipped)
        for word in words
    )


def _fragments(
    items: Sequence[Any],  # np. [{"tekst": "Bogumił", "rodzaj": "IMIĘ"}]
) -> list[tuple[str, str]]:
    """
    Description:
    Fragmenty i rodzaje z elementów odpowiedzi; pusty fragment odpada. Element spoza schematu
    to błąd, a nie pominięcie: pominięty element to osoba, która przeszłaby dalej.

    Example args:
        items=[{"tekst": " Bogumił ", "rodzaj": "IMIĘ"}, {"tekst": "", "rodzaj": "NAZWISKO"}]

    Example result:
        [("Bogumił", "IMIĘ")]

    Raises:
        LLMError: element nie jest obiektem z tekstem i rodzajem z `PERSON_KINDS`
    """
    fragments = []

    for item in items:
        fragment = item.get("tekst") if isinstance(item, dict) else None
        kind     = item.get("rodzaj") if isinstance(item, dict) else None

        if not isinstance(fragment, str) or kind not in PERSON_KINDS:
            raise LLMError("element odpowiedzi węzła osób jest poza schematem")

        if fragment.strip():
            fragments.append((fragment.strip(), kind))

    return fragments
