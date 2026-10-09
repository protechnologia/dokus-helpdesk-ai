from collections.abc import Sequence


def contains_all(
    text:        str,            # np. "throw new Blad('Z serwerem nie udało się skomunikować');"
    parts:       Sequence[str],  # np. ["skomunikować", "serwerem"]
    *,                           # kolejny argument podaje się wyłącznie po nazwie
    ignore_case: bool,           # True: wielkość liter nie ma znaczenia
) -> bool:
    """
    Description:
    Mówi, czy tekst zawiera wszystkie podane ciągi znaków, w dowolnej kolejności. Ciąg to nie
    wyraz: „serwer" jest zawarty w „serwerem".

    Czy wielkość liter się liczy, wołający mówi za każdym razem wprost — wartości domyślnej nie
    ma, bo zwykle musi się ona zgadzać z czymś obok: z flagą programu albo z zapytaniem do bazy,
    które sprawdza resztę warunku.

    Example args:
        text="throw new Blad('Z serwerem nie udało się skomunikować');"
        parts=["SKOMUNIKOWAĆ", "serwerem"]
        ignore_case=True

    Example result:
        True
    """
    # --- wielkość liter się liczy: porównanie znak w znak ---
    if not ignore_case:
        return all(part in text for part in parts)

    # --- bez względu na wielkość liter: `casefold()` obejmuje też litery spoza ASCII ---
    folded = text.casefold()

    return all(part.casefold() in folded for part in parts)
