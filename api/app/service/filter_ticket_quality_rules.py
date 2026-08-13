"""
Description:
The rules of the quality filter — one function per rule, each returning the fragment that made it
fire, or None.

Why they live apart from `filter_ticket_quality.py`: rules keep arriving (every measurement over a
larger corpus suggests another), while the orchestrator around them practically never changes. Two
files, two rates of change.

Why plain functions rather than methods: each is a stateless read of one record, so a class would
add nothing but a place to put `self` (CLAUDE.md -> "Warstwy kodu": function or class is decided by
state). `RULES` at the bottom is what the orchestrator iterates, so it never names a rule itself and
adding one means appending to a tuple.

**Every rule reads `solution`, and never `cause` — that is measured, not assumed.** An empty `cause`
looks like the obvious signal and is not: 114 of the 200 measured records declare no cause and 105
of them are perfectly good (2026-08-13). Tickets do get solved without anyone naming the cause, so a
filter built on that field would gut the corpus.

**The labels these rules were measured against are not independent ground truth** — they were
produced by a model reading the same artifacts. The numbers below therefore measure AGREEMENT with
an earlier review, not correctness; disagreements are records worth a human look, not proof the
rules are wrong.
"""

import re

# The schema's explicit ways of saying "there is nothing here" (NO_VALUE, NOT_APPLICABLE in
# `model/ticket_parsed.py`), plus the two phrasings the parsing prompt produces around them.
#
# THIS IS THE POINT OF THE WHOLE RULE: it reads the CONTRACT, not the model's prose. Every field may
# say "brak" instead of being left out, the parsing prompt lives in the repo under a guard test, and
# it is deliberately not configurable (rule 7). A different model gets the same prompt with the same
# escape phrases — so unlike a rule tuned to one model's turn of phrase, this one survives swapping
# the model. Editing these phrases in the prompt IS an edit to this filter; the prompt file says so,
# and the guard test on the reference corpus fails loudly if the two drift apart.
#
# `brak` is matched as a WHOLE WORD, never as a prefix. "Dodano brakujące ustawienie systemowe"
# describes work that was done, and `brak\w*` turned it into a rejection (measured: one false
# positive, gone after this change).
ESCAPE_PHRASE = re.compile(r"\b(brak|nie dotyczy|nie ustalono|nie podano)\b", re.I)

# How many words may remain beside the escape phrase before the field counts as content.
#
# Measured on the 200-record reference corpus (2026-08-13): at this threshold the rule drops 29 of
# 38 labelled records with ZERO false positives, and every value from 4 to 10 gives the same clean
# split — a wide margin, not a number tuned to the data. The reasoning is plain: an empty record
# says "brak rozstrzygnięcia w wątku" and stops, while a REFUSAL — the most valuable class in this
# corpus, telling the reader what NOT to attempt — has to explain itself and therefore runs long
# ("Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować…").
#
# Expect to revisit this number on the full corpus; it belongs to this corpus and this parser, which
# is why it is a named constant rather than a literal buried in a comparison.
MAX_HOLLOW_EXTRA_WORDS = 10

# How much of the field goes into the report. Enough to recognise the sentence, short enough that a
# 200-record run stays readable.
EVIDENCE_LENGTH = 80


def no_resolution(
    solution: str,  # e.g. "Brak rozstrzygnięcia w wątku."
) -> str | None:
    """
    Description:
    Fires when `solution` admits there is no resolution and adds little else — the record closes
    without saying what was wrong or what was done, so there is nothing to propose to anyone else.

    Two steps, and the second is what makes it safe: find an escape phrase anywhere in the field,
    then count what remains once the escape wording is removed. Little left means the field is
    hollow; plenty left means the "brak" opens a real statement (a refusal, an explanation of
    unchanged behaviour) and the record stays.

    Measured: 29 of 38 labelled rejections, no false positives (2026-08-13).

    Example args:
        solution="Brak rozstrzygnięcia w wątku."

    Example result:
        "Brak rozstrzygnięcia w wątku."

    Example args:
        solution="Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować…"

    Example result:
        None — a refusal is content, not emptiness
    """
    # --- does the record admit to nothing at all? ---
    if not ESCAPE_PHRASE.search(solution):
        return None

    # --- how much is left once the admission is taken out? ---
    # The same pattern both finds the admission and removes it: a separate "hollow words" list was
    # measured against this and earned nothing at the chosen threshold (identical 29/38, zero false
    # positives), so it was one more thing to keep in sync for no gain.
    remainder = ESCAPE_PHRASE.sub(" ", solution)

    if len(re.findall(r"\w+", remainder)) > MAX_HOLLOW_EXTRA_WORDS:
        return None

    return solution.strip()[:EVIDENCE_LENGTH]


# Every rule, in the order the report lists them. The orchestrator iterates this tuple and knows no
# rule by name, so adding one means appending here — and the tests parametrise over it rather than
# over a hardcoded count.
#
# One rule today, deliberately. Patterns for the remaining nine rejections (a promise in the future
# tense, a pointer to a duplicate ticket, a ticket carrying several unrelated matters) each caught
# one or two records while depending on one model's exact wording — the fragile half of the trade,
# for a fraction of the yield. They come back if a larger corpus shows they are worth it.
RULES = (
    no_resolution,
)
