"""
Description:
Rozbiór tekstu z liniami z numerami, który oddają `read_code_file` i `read_code_symbol`.
"""


def numbered_pairs(
    numbered_lines: str,  # np. "12\t    {\n13\t        return $numer;"
) -> list[tuple[int, str]]:
    """
    Description:
    Rozbiera tekst z numerami na pary „numer, treść", w kolejności linii. Numer oddziela od treści
    pierwszy tabulator, więc tabulator w treści linii zostaje w niej.

    Example args:
        numbered_lines="12\t    {\n13\t        return $numer;"

    Example result:
        [(12, "    {"), (13, "        return $numer;")]
    """
    pairs: list[tuple[int, str]] = []

    for line in numbered_lines.split("\n"):
        number, text = line.split("\t", 1)
        pairs.append((int(number), text))

    return pairs


def line_numbers(
    numbered_lines: str,  # np. "12\t    {\n13\t        return $numer;"
) -> list[int]:
    """
    Description:
    Same numery linii z tekstu z numerami, w kolejności.

    Example args:
        numbered_lines="12\t    {\n13\t        return $numer;"

    Example result:
        [12, 13]
    """
    return [number for number, _ in numbered_pairs(numbered_lines)]


def line_texts(
    numbered_lines: str,  # np. "12\t    {\n13\t        return $numer;"
) -> list[str]:
    """
    Description:
    Sama treść linii z tekstu z numerami, w kolejności, znak w znak.

    Example args:
        numbered_lines="12\t    {\n13\t        return $numer;"

    Example result:
        ["    {", "        return $numer;"]
    """
    return [text for _, text in numbered_pairs(numbered_lines)]
