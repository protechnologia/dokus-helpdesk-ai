"""
Description:
Tnie treść sekcji dokumentacji na fragmenty, z których embedder liczy wektory, i składa tekst
jednego fragmentu. Cała sekcja zostaje w Postgresie i w tej postaci czyta ją agent; fragmenty
istnieją tylko po to, żeby wyszukiwanie po znaczeniu trafiało w szczegół z długiej sekcji —
jeden wektor na długą sekcję taki szczegół gubi, a ponad 8192 tokeny embedder ucina bez błędu.

| funkcja                  | co robi                                           |
|--------------------------|---------------------------------------------------|
| `split_into_fragments()` | treść sekcji → fragmenty nie dłuższe niż limit    |
| `build_fragment_text()`  | tytuł sekcji + fragment → tekst do embeddingu     |

Przed — treść sekcji, limit 120 znaków:

    Kody uprawnień nadaje się w Ustawienia → Uprawnienia → Stanowiska.

    ### Kancelaria

    - `KANC_PODGLAD` — przeglądanie korespondencji (Referent).
    - `KANC_EDYCJA` — edycja korespondencji (Kancelista).

    ### Pieczęć elektroniczna

    - `PIECZEC_UZYCIE` — opatrywanie dokumentów pieczęcią urzędu.

Po — trzy fragmenty:

    Kody uprawnień nadaje się w Ustawienia → Uprawnienia → Stanowiska.

    ### Kancelaria

    - `KANC_PODGLAD` — przeglądanie korespondencji (Referent).
    - `KANC_EDYCJA` — edycja korespondencji (Kancelista).

    ### Pieczęć elektroniczna

    - `PIECZEC_UZYCIE` — opatrywanie dokumentów pieczęcią urzędu.

Co się dzieje po drodze:

1. Treść dzieli się na akapity, czyli bloki rozdzielone pustą linią. Lista albo tabela bez
   pustych linii to jeden akapit.
2. Akapit dłuższy niż limit dzieli się na linie, linia dłuższa niż limit na zdania, zdanie na
   słowa, a słowo dłuższe niż limit jest cięte co limit znaków.
3. Kolejne kawałki trafiają do fragmentu, dopóki mieszczą się w limicie.
4. Nagłówek nie kończy fragmentu: przechodzi do następnego, razem z blokiem, który opisuje.
   W przykładzie „### Kancelaria" zmieściłoby się w pierwszym fragmencie, ale stoi w drugim.
5. Do embeddingu idzie tytuł sekcji i fragment. Bez tytułu wycinek ze środka długiej sekcji
   nie mówi, czego dotyczy.

O czym pamiętać przy zmianach:

- Zmiana tych funkcji albo limitu zmienia wektory, więc wymaga ponownego `helpdesk docs index`.
- Limit jest miękki w jednym miejscu: fragment zaczynający się od przeniesionego nagłówka może
  przekroczyć go o długość tego nagłówka (w przykładzie drugi fragment ma 128 znaków).
- Koniec zdania to kropka, wykrzyknik albo pytajnik przed odstępem, więc bywa nim też skrót
  („np."). Ma to znaczenie tylko wtedy, gdy cięcie wypadnie akurat w tym miejscu.
- Fragmenty nie nachodzą na siebie. Długość fragmentu rozstrzyga pomiar (CLAUDE.md -> p. 8).
"""

import re

# Akapity rozdziela pusta linia — także taka, w której zostały spacje. Wzorzec zabiera też
# spacje z końca akapitu przed nią; wcięcie następnego akapitu zostaje.
PARAGRAPH_BREAK     = re.compile(r"\s*\n\s*\n")
PARAGRAPH_SEPARATOR = "\n\n"

# Coraz drobniejsze podziały akapitu, który nie mieści się w limicie. Każdy poziom mówi, czym
# dzielić i czym złożyć kawałki z powrotem.
FINER_LEVELS = (
    (re.compile(r"\n"),             "\n"),  # linie
    (re.compile(r"(?<=[.!?…])\s+"), " "),   # zdania: odstęp po kropce, wykrzykniku, pytajniku
    (re.compile(r"\s+"),            " "),   # słowa
)

# Nagłówek markdown: od jednego do sześciu `#` i odstęp.
HEADING = re.compile(r"#{1,6}\s")


def split_into_fragments(
    body:      str,  # treść pliku `.md` sekcji
    max_chars: int,  # np. 1500 — RAG_DOCS_FRAGMENT_CHARS
) -> list[str]:
    """
    Description:
    Tnie treść sekcji po akapitach na fragmenty nie dłuższe niż limit, w kolejności treści.
    Sekcja krótsza niż limit to jeden fragment; pusta treść nie daje żadnego.

    Example args:
        body="Kody uprawnień nadaje się w…\\n\\n### Kancelaria\\n\\n- `KANC_PODGLAD` — …"
        max_chars=120

    Example result:
        ["Kody uprawnień nadaje się w…", "### Kancelaria\\n\\n- `KANC_PODGLAD` — …", …]
    """
    paragraphs = PARAGRAPH_BREAK.split(body.strip())
    pieces     = [
        piece
        for paragraph in paragraphs
        if paragraph.strip()
        for piece in _fit(paragraph, max_chars, FINER_LEVELS)
    ]
    fragments  = _pack(pieces, PARAGRAPH_SEPARATOR, max_chars)

    return fragments


def build_fragment_text(
    title:    str,  # np. "Wykaz uprawnień"
    fragment: str,  # np. "### Pieczęć elektroniczna\n\n- `PIECZEC_UZYCIE` — …"
) -> str:
    """
    Description:
    Składa tekst, z którego embedder liczy wektor fragmentu: tytuł sekcji i fragment, każde
    od nowej linii.

    Example args:
        title="Wykaz uprawnień"
        fragment="### Pieczęć elektroniczna\\n\\n- `PIECZEC_UZYCIE` — opatrywanie dokumentów…"

    Example result:
        "Wykaz uprawnień\\n### Pieczęć elektroniczna\\n\\n- `PIECZEC_UZYCIE` — opatrywanie…"
    """
    return f"{title}\n{fragment}"


def _fit(
    text:      str,                                      # np. akapit: lista kodów uprawnień
    max_chars: int,                                      # np. 1500
    levels:    tuple[tuple[re.Pattern[str], str], ...],  # np. FINER_LEVELS — czym jeszcze dzielić
) -> list[str]:
    """
    Description:
    Oddaje tekst w kawałkach nie dłuższych niż limit. Tekst, który się mieści, wraca bez zmian;
    dłuższy jest dzielony na pierwszym poziomie i składany z powrotem do limitu, a to, co nadal
    się nie mieści — na kolejnym.

    Example args:
        text="- `KANC_PODGLAD` — przeglądanie…\\n- `KANC_EDYCJA` — edycja…"
        max_chars=40
        levels=FINER_LEVELS

    Example result:
        ["- `KANC_PODGLAD` — przeglądanie…", "- `KANC_EDYCJA` — edycja…"]
    """
    # --- mieści się: nic do dzielenia ---
    if len(text) <= max_chars:
        return [text]

    # --- nie ma już czym dzielić: jedno „słowo" dłuższe niż limit, cięte co limit znaków ---
    if not levels:
        return [text[start : start + max_chars] for start in range(0, len(text), max_chars)]

    # --- dzielimy na tym poziomie, a za długie części na kolejnych ---
    pattern, joiner = levels[0]
    pieces          = [
        piece
        for part in pattern.split(text)
        if part.strip()
        for piece in _fit(part, max_chars, levels[1:])
    ]

    return _pack(pieces, joiner, max_chars)


def _pack(
    pieces:    list[str],  # np. ["Wstęp…", "### Kancelaria", "- `KANC_PODGLAD` — …"]
    separator: str,        # np. "\n\n" — czym łączyć kawałki w jednym fragmencie
    max_chars: int,        # np. 1500
) -> list[str]:
    """
    Description:
    Łączy kolejne kawałki w fragmenty, dokładając następny, dopóki całość mieści się w limicie.
    Nagłówek, który zostałby na końcu fragmentu, przechodzi do następnego.

    Example args:
        pieces=["Wstęp do wykazu.", "### Kancelaria", "- `KANC_PODGLAD` — przeglądanie…"]
        separator="\\n\\n"
        max_chars=60

    Example result:
        ["Wstęp do wykazu.", "### Kancelaria\\n\\n- `KANC_PODGLAD` — przeglądanie…"]
    """
    fragments: list[list[str]] = []
    current:   list[str]       = []

    for piece in pieces:
        # --- kawałek się nie mieści: zamknij fragment i zacznij następny ---
        if current and len(separator.join([*current, piece])) > max_chars:
            # Nagłówek bez swojego bloku nic nie mówi, a blok bez nagłówka traci temat.
            carried = [current.pop()] if HEADING.match(current[-1]) else []

            if current:
                fragments.append(current)

            current = carried

        current.append(piece)

    # --- ostatni, niedomknięty fragment ---
    if current:
        fragments.append(current)

    return [separator.join(fragment) for fragment in fragments]
