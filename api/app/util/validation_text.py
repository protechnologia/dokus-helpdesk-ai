from pydantic import ValidationError


def describe_validation_error(error: ValidationError) -> list[str]:   # e.g. 2 field errors
    """
    Description:
    Flattens a pydantic error into one readable line per problem.

    Do czego:
    Formats, never validates — it knows nothing about tickets and would read any pydantic model's
    failure the same way, which is what puts it in `util/`. Both callers
    (`parser_ticket_parsed.py` reporting a rejected LLM answer, `validator_ticket_parsed.py`
    reporting a bad file) run over a whole corpus and produce hundreds of these, so the output has
    to name the field: "resolution: …" is actionable, a raw pydantic dump is not.

    Not confused with `app/errors.py`, which registers HTTP exception handlers — this one only
    turns a validation failure into lines a human reads in a CLI report.

    Example args:
        error=ValidationError(...)

    Example result:
        ["resolution: Value error, resolution='zamkniete' spoza słownika"]
    """
    lines: list[str] = []

    for entry in error.errors():
        # Model-level validators report an empty location; name them for what they are.
        location = ".".join(str(part) for part in entry["loc"]) or "rekord"
        lines.append(f"{location}: {entry['msg']}")

    return lines
