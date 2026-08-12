import html
import re

# Block-level tags become a line break so paragraphs do not run together once the tags are gone;
# a naive strip would turn "<p>Krok 1</p><p>Krok 2</p>" into "Krok 1Krok 2".
_BLOCK_TAG   = re.compile(r"</(?:p|div|li|tr|h[1-6])>|<br\s*/?>", re.IGNORECASE)
_ANY_TAG     = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n{3,}")


def strip_html(raw: str) -> str:   # e.g. "<p>Dzień dobry,</p><p>Nie działa&#039;</p>"
    """
    Description:
    Turns an HTML fragment into plain text. Knows nothing about tickets — every source adapter
    needs it (today the file one, in stage 10 the SQL one), which is why it lives in `util/`
    rather than next to one of them.

    Runs before anything else reads the content: tags and entities in the prompt cost tokens,
    split words the model needs whole, and would land verbatim in the artifact (CLAUDE.md ->
    "Pułapki tej bazy").

    Order matters — entities are unescaped LAST. Doing it first would turn a `&lt;p&gt;` written by
    a user into a real tag, which the tag pass would then delete along with the text around it.

    Example args:
        raw="<p>Dzień dobry,</p><p>Nie działa wysyłka&#039;</p>"

    Example result:
        "Dzień dobry,\\nNie działa wysyłka'"
    """
    with_breaks  = _BLOCK_TAG.sub("\n", raw)
    without_tags = _ANY_TAG.sub("", with_breaks)
    # Resolves against the standard library, not this module: Python 3 has no implicit relative
    # imports, so `import html` here is stdlib even though the file shares its name.
    unescaped    = html.unescape(without_tags)

    # Collapse the runs of blank lines the tag removal leaves behind.
    lines = [line.strip() for line in unescaped.splitlines()]

    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()
