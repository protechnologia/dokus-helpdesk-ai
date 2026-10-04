from pydantic import ValidationError


def describe_validation_error(
    error: ValidationError,  # np. 2 błędy pól
) -> list[str]:
    """
    Description:
    Spłaszcza błąd pydantica do jednej czytelnej linii na problem.

    Do czego:
    Formatuje, nigdy nie waliduje — nie wie nic o zgłoszeniach i tak samo czyta porażkę dowolnego
    modelu pydantica, i to stawia ją w `core_util/`. Wołający (`validator_ticket_parsed.py`
    raportujący zły plik) przechodzi po całym korpusie i produkuje setki takich linii, więc wynik
    musi nazywać pole: „resolution: …" da się naprawić, surowy zrzut pydantica nie.

    Nie mylić z `app/errors.py`, który rejestruje handlery wyjątków HTTP — ta funkcja tylko zamienia
    porażkę walidacji na linie, które człowiek czyta w raporcie CLI.

    Example args:
        error=ValidationError(...)

    Example result:
        ["resolution: Value error, resolution='zamkniete' spoza słownika"]
    """
    lines: list[str] = []

    for entry in error.errors():
        # Walidatory poziomu modelu zgłaszają pustą lokalizację — nazwij je tym, czym są.
        location = ".".join(str(part) for part in entry["loc"]) or "rekord"
        lines.append(f"{location}: {entry['msg']}")

    return lines
