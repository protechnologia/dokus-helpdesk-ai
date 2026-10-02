from app.tools import SourceRef


def merge_sources(
    current: list[SourceRef],  # np. [SourceRef(source="find_tickets", item_id="90001", …)]
    new:     list[SourceRef],  # np. [SourceRef(source="find_tickets", item_id="90001", …), …]
) -> list[SourceRef]:
    """
    Description:
    Reduktor pola `sources` w stanie grafu: dokleja nowe źródła, pomijając te, których klucz już
    jest. Agent może szukać kilka razy i trafić na to samo zgłoszenie — na liście źródeł ma się
    ono znaleźć raz, z pierwszego trafienia.

    Wspólny dla wszystkich grafów, choć każdy ma własny `state.py`: graf ze źródłami deklaruje
    pole jako `Annotated[list[SourceRef], merge_sources]`, a test grafów (p. 12) pilnuje, że żaden
    o tym nie zapomniał. Wiadomości łączy `operator.add`.

    Example args:
        current=[SourceRef(…, item_id="90001")]
        new=[SourceRef(…, item_id="90001"), SourceRef(…, item_id="90002")]

    Example result:
        [SourceRef(…, item_id="90001"), SourceRef(…, item_id="90002")]
    """
    seen = {ref.key for ref in current}

    return current + [ref for ref in new if ref.key not in seen]
