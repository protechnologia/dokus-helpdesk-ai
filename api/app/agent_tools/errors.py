class ToolCallError(Exception):
    """
    Description:
    Wywołania narzędzia nie da się wykonać z powodu tego, o co agent poprosił: narzędzia, którego
    nie ma, błędnych argumentów albo identyfikatora, którego nie ma w bazie.

    Do czego:
    Po tej klasie węzeł `run_tools` rozpoznaje błąd, który ma wrócić do modelu jako wynik
    narzędzia (`{"error": …}`), żeby model poprawił wywołanie, a przebieg szedł dalej. Błędy
    własne narzędzi (`errors.py` w katalogu narzędzia) po niej dziedziczą; sam węzeł zgłasza ją
    za nieznane narzędzie i za argumenty, które nie przeszły walidacji.

    Wszystko inne — awaria embeddera, Qdranta albo Postgresa — tą klasą NIE jest: zatrzymuje
    przebieg, a trasa oddaje 503. Poprawione wywołanie niczego by tam nie zmieniło.

    Komunikat czyta model, więc mówi, co było nie tak, i wymienia wyłącznie nazwy
    i identyfikatory, nigdy treść zgłoszenia.
    """
