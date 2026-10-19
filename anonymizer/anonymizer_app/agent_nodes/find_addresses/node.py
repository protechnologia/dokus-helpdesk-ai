"""
Description:
Węzeł `find_addresses` grafu anonimizacji (p. 19.5): model anonimizujący wskazuje adresy,
których nie złapały wzorce — bez kodu pocztowego i bez słowa przed ulicą, w odmianie, małymi
literami, złamane na dwie linie — a kod znajduje je w tekście i odsiewa to, co adresem nie jest.
Biegnie równolegle z węzłem osób, na tych samych częściach tekstu.

Przykład (zmyślony):

    tekst:   „Mieszka na brzozowej 12\\nw sulejowie, a pismo z {ADRES} wróciło.”
    model:   „brzozowej 12”, „sulejowie”, „{ADRES}”
    miejsca: „brzozowej 12”, „sulejowie” (linia tuż obok ulicy z numerem)
    po:      „Mieszka na {ADRES}\\nw {ADRES}, a pismo z {ADRES} wróciło.”

Kroki:

1. Model wskazuje adresy w każdej części tekstu (`ask_model()`).
2. Odpada fragment ze znacznikiem (model powtarza adres zamieniony już przez wzorce) i sam kod
   pocztowy (sam nie wskazuje osoby).
3. Każdy fragment szuka się w tekście (`place_address()`): dosłownie z dowolnymi odstępami, bez
   względu na wielkość liter, częściami między przecinkami i liniami, a na końcu po początku
   każdego słowa (model podaje czasem adres w mianowniku: „Brzozowa 12” zamiast
   „brzozowej 12”).
4. Miejsce bez cyfry zostaje tylko wtedy, gdy styka się z miejscem z cyfrą (dzielą je najwyżej
   przecinek i odstępy: „Garwolin, Kościelna 8”) albo stoi w linii tuż obok niego (adres złamany
   na dwie linie). Tak odpada nazwa urzędu, miejscowość ze stopki i ścieżka menu.

O czym pamiętać przy zmianach:

- Bez filtrów z kroków 2 i 4 sonda z 2026-10-18 wskazała w próbce korpusu 24 fragmenty spoza
  zaznaczeń (15 ze znacznikiem, 9 bez cyfry), a z nimi — żadnego, bez straty adresu.
- Filtr bez cyfry działa na miejscu, nie na fragmencie: miejscowość dopasowana jako część
  fragmentu z numerem nie zamienia się wszędzie, gdzie stoi w tekście.
"""

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
from anonymizer_app.core_util.fold import fold_text, fold_word
from anonymizer_app.core_util.spans import is_inside
from anonymizer_app.engine_llm import LLMClient

# Katalog promptu węzła: `prompt_system.md` i `examples.json` leżą obok tego pliku.
PROMPT_DIR = Path(__file__).parent

# Rodzaj, zarazem nazwa znacznika — ten sam co adresu ze wzorców.
ADDRESS_KIND = "ADRES"

# Schemat odpowiedzi: lista napisów. Klucz po polsku, jak w prompcie, z którym go mierzono.
SCHEMA_NAME = "adresy"
ITEMS_KEY   = "adresy"
SCHEMA      = {
    "type":       "object",
    "properties": {ITEMS_KEY: {"type": "array", "items": {"type": "string"}}},
    "required":   [ITEMS_KEY],
}

# Limit odpowiedzi na część tekstu. Na dwóch wątkach próbki korpusu model zapętlał odpowiedź
# (jeden fragment ze znacznikiem 285 razy, około 40 s); 300 tokenów skróciło najdłuższe wywołanie
# do 10 s bez straty adresu (sonda z 2026-10-18). Pełne elementy uciętej odpowiedzi czyta
# `answer_items()`.
MAX_ANSWER_TOKENS = 300

# Sam kod pocztowy: odpada, bo sam nie wskazuje osoby.
POSTAL_CODE_ONLY = re.compile(r"\s*\d{2}-\d{3}\s*")

# Co może dzielić miejscowość od ulicy z numerem, żeby się „stykały”: przecinek i odstępy w jednej
# linii, także twarda spacja.
TOUCHING_GAP = re.compile(r"[ \t\xa0,]*")

# Granice fragmentu i części: przecinek albo nowa linia.
PART_SEPARATOR = re.compile(r",|\n")

# Słowo: litery i cyfry.
WORD = re.compile(r"[^\W_]+")

# Co może stać między słowami adresu szukanego po początku: wszystko, co nie jest literą ani cyfrą.
BETWEEN_WORDS = r"[\W_]+"

# Słowo krótsze niż tyle liter szuka się dosłownie, a nie po początku.
MIN_STEM_LETTERS = 4

# Ile ostatnich liter słowa może się różnić i ile liter może stać po jego początku w tekście —
# ta sama reguła co przy odmianach osób (`core_service/finder_word_forms.py`).
ENDING_LETTERS   = 2
MAX_TAIL_LETTERS = 4


class FindAddressesNode(Node):
    """
    Description:
    Węzeł grafu, który pyta model o adresy i zamienia jego odpowiedź na miejsca w całym tekście;
    przebieg opisuje docstring modułu. Miejsca mogą na siebie zachodzić — wybiera z nich węzeł
    `replace_found`.
    """

    name = "find_addresses"

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
            FindAddressesNode gotowy do `run()`
        """
        self._llm = llm

    async def run(
        self,
        state: BaseModel,  # np. AnonymizeState(after_patterns="Mieszka na brzozowej 12…", …)
    ) -> dict[str, Any]:
        """
        Description:
        Pyta model o każdą część tekstu, a miejsca wskazanych adresów w `after_patterns` zapisuje
        w `addresses`; w logu liczba fragmentów od modelu i liczba miejsc.

        Example args:
            state=AnonymizeState(after_patterns="Mieszka na brzozowej 12\\nw sulejowie…",
                                 chunks=["Mieszka na brzozowej 12\\nw sulejowie…"])

        Example result:
            {"addresses": [Found(kind="ADRES", start=11, end=23), …],
             "log": [LogEntry(node="find_addresses", message="3 fragmentów → 2 miejsc")]}

        Raises:
            EngineConfigError: serwer modelu odrzucił klucz albo nie zna modelu
            LLMError: model nie odpowiedział albo odpowiedział spoza schematu
        """
        items = await ask_model(self._llm, PROMPT_DIR, state.chunks, SCHEMA_NAME, SCHEMA, ITEMS_KEY,
                                MAX_ANSWER_TOKENS)
        found = place_addresses(state.after_patterns, items)

        update = {
            "addresses": found,
            "log":       [self.log_entry(f"{len(items)} fragmentów → {len(found)} miejsc")],
        }

        return update


def place_addresses(
    text:  str,            # tekst po wzorcach, np. "Mieszka na brzozowej 12\nw sulejowie…"
    items: Sequence[Any],  # elementy odpowiedzi modelu, np. ["brzozowej 12", "sulejowie"]
) -> list[Found]:
    """
    Description:
    Miejsca adresów w całym tekście z elementów odpowiedzi modelu, według kroków 2–4 z opisu
    modułu, każde raz.

    Example args:
        text="Mieszka na brzozowej 12\\nw sulejowie, a pismo z {ADRES} wróciło."
        items=["brzozowej 12", "sulejowie", "{ADRES}"]

    Example result:
        [Found(kind="ADRES", start=11, end=23), Found(kind="ADRES", start=26, end=35)]

    Raises:
        LLMError: element odpowiedzi nie jest napisem
    """
    # --- fragmenty, które mogą być adresem z tekstu ---
    kept = [
        fragment
        for fragment in _fragments(items)
        if "{" not in fragment and not POSTAL_CODE_ONLY.fullmatch(fragment)
    ]

    spans = [span for fragment in kept for span in place_address(text, fragment)]

    # --- miejsca bez cyfry tylko przy ulicy z numerem ---
    with_digit = [span for span in spans if _has_digit(text[span[0]:span[1]])]
    near       = [
        span
        for span in spans
        if not _has_digit(text[span[0]:span[1]]) and _next_to(text, span, with_digit)
    ]

    # Każde miejsce raz: ten sam adres wskazany w kilku częściach daje te same zakresy.
    found = list(dict.fromkeys(
        Found(kind=ADDRESS_KIND, start=start, end=end) for start, end in with_digit + near
    ))

    return found


def place_address(
    text:     str,  # np. "Mieszka na brzozowej 12\nw sulejowie."
    fragment: str,  # np. "Brzozowa 12"
) -> list[tuple[int, int]]:
    """
    Description:
    Zakresy fragmentu w tekście, poza znacznikami, pierwszą drogą, która coś znajdzie: dosłownie
    z dowolnymi odstępami, bez względu na wielkość liter, częściami między przecinkami i liniami,
    po początku każdego słowa.

    Example args:
        text="Mieszka na brzozowej 12\\nw sulejowie."
        fragment="Brzozowa 12"

    Example result:
        [(11, 23)]
    """
    fragment = fragment.strip()
    tokens   = fragment.split()

    if not tokens:
        return []

    markers = marker_spans(text)

    # --- cały fragment: dosłownie, a potem bez względu na wielkość liter ---
    joined = r"\s+".join(re.escape(token) for token in tokens)

    for flags in (0, re.IGNORECASE):
        pattern = re.compile(rf"(?<![^\W_]){joined}(?![^\W_])", flags)
        spans   = [
            match.span()
            for match in pattern.finditer(text)
            if not is_inside(match.span(), markers)
        ]

        if spans:
            return spans

    # --- części między przecinkami i liniami: adres podany w innym układzie niż w tekście ---
    parts = [part for part in PART_SEPARATOR.split(fragment) if part.strip() != fragment]
    spans = [span for part in parts if part.strip() for span in place_address(text, part)]

    if spans:
        return spans

    return _stem_spans(text, fragment, markers)


def _stem_spans(
    text:     str,                    # np. "Mieszka na brzozowej 12 w sulejowie."
    fragment: str,                    # np. "Brzozowa 12"
    markers:  list[tuple[int, int]],  # zakresy znaczników w tekście
) -> list[tuple[int, int]]:
    """
    Description:
    Zakresy fragmentu w innej odmianie niż w tekście: każde słowo po początku (bez dwóch
    ostatnich liter, najwyżej cztery litery końcówki), liczba i krótkie słowo dosłownie, między
    nimi dowolne znaki niebędące literą ani cyfrą. Szuka w tekście złożonym znak po znaku, więc
    zakresy wskazują oryginał.

    Example args:
        text="Mieszka na brzozowej 12 w sulejowie."
        fragment="Brzozowa 12"
        markers=[]

    Example result:
        [(11, 23)]
    """
    parts = []

    for token in WORD.findall(fragment):
        folded = fold_word(token)

        if any(char.isdigit() for char in token) or len(folded) < MIN_STEM_LETTERS:
            parts.append(re.escape(folded))
            continue

        stem = folded[:max(3, len(folded) - ENDING_LETTERS)]
        parts.append(rf"{re.escape(stem)}[^\W\d_]{{0,{MAX_TAIL_LETTERS}}}")

    if not parts:
        return []

    pattern = re.compile(rf"(?<![^\W_]){BETWEEN_WORDS.join(parts)}(?![^\W_])")
    spans   = [
        match.span()
        for match in pattern.finditer(fold_text(text))
        if not is_inside(match.span(), markers)
    ]

    return spans


def _next_to(
    text:       str,                    # np. "Kasztanowa 7\nPiaseczno"
    span:       tuple[int, int],        # miejsce bez cyfry, np. (13, 22)
    with_digit: list[tuple[int, int]],  # miejsca z cyfrą, np. [(0, 12)]
) -> bool:
    """
    Description:
    Mówi, czy miejsce bez cyfry styka się z miejscem z cyfrą (dzielą je najwyżej przecinek
    i odstępy w jednej linii) albo stoi w linii tuż przed nim lub tuż po nim.

    Example args:
        text="Kasztanowa 7\\nPiaseczno"
        span=(13, 22)
        with_digit=[(0, 12)]

    Example result:
        True
    """
    line = text.count("\n", 0, span[0])

    for start, end in with_digit:
        # --- zachodzą na siebie: część tego samego adresu ---
        if span[0] < end and start < span[1]:
            return True

        gap = text[span[1]:start] if span[1] <= start else text[end:span[0]]

        # --- styka się w jednej linii: „Garwolin, Kościelna 8” ---
        if TOUCHING_GAP.fullmatch(gap):
            return True

        # --- linia tuż obok: adres złamany na dwie linie ---
        digit_lines = {text.count("\n", 0, start), text.count("\n", 0, end)}

        if {line - 1, line + 1} & digit_lines:
            return True

    return False


def _has_digit(
    text: str,  # np. "brzozowej 12"
) -> bool:
    """
    Description:
    Mówi, czy w tekście stoi choć jedna cyfra.

    Example args:
        text="brzozowej 12"

    Example result:
        True
    """
    return any(char.isdigit() for char in text)


def _fragments(
    items: Sequence[Any],  # np. ["brzozowej 12", " sulejowie "]
) -> list[str]:
    """
    Description:
    Fragmenty z elementów odpowiedzi; pusty fragment odpada. Element, który nie jest napisem, to
    błąd, a nie pominięcie: pominięty element to adres, który przeszedłby dalej.

    Example args:
        items=["brzozowej 12", " sulejowie ", ""]

    Example result:
        ["brzozowej 12", "sulejowie"]

    Raises:
        LLMError: element nie jest napisem
    """
    if not all(isinstance(item, str) for item in items):
        raise LLMError("element odpowiedzi węzła adresów jest poza schematem")

    return [item.strip() for item in items if item.strip()]
