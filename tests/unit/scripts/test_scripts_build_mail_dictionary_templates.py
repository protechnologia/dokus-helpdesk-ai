"""
Description:
Liczenie słownika szablonów w `scripts/build_mail_dictionary.py` (`build_templates`), na
zmyślonych zgłoszeniach w pamięci: szablonem jest fragment 12 słów, który stoi w co najmniej
podanej liczbie RÓŻNYCH wątków kanału.
"""

from datetime import date as Date

from build_mail_dictionary import build_templates

from app.core_util.repetition import run_digest, words_of
from tests._helpers.mail import mail_ticket

# Wspólny fragment wątków, dłuższy niż 12 słów, jak stopka poufności.
FOOTER = "Ta wiadomość i jej załączniki są poufne i przeznaczone wyłącznie dla wskazanego odbiorcy."

# Dzień budowy w próbkach; słownik zapisuje go w metryczce.
BUILT_ON = Date(2026, 11, 20)


def test_a_fragment_shared_by_enough_threads_becomes_a_template() -> None:
    """Sprawdza, czy fragment stojący w trzech różnych wątkach jest szablonem przy progu
    3 wątków, a przy progu 4 nie jest, i czy słownik zapisuje liczbę wątków, długość ciągu
    i próg.

    Wyłapuje próg porównywany odwrotnie albo o jeden przesunięty: słownik łapałby fragmenty
    jednej sprawy albo gubił stopki stojące dokładnie w tylu wątkach, ile wynosi próg."""
    tickets = [mail_ticket(f"Sprawa numer {number}.\n{FOOTER}") for number in range(3)]
    digest  = run_digest(words_of(FOOTER)[:12])

    templates = build_templates(tickets, 12, 3, "korpus", BUILT_ON)

    assert digest in templates.digests
    assert (templates.threads, templates.run_words, templates.min_threads) == (3, 12, 3)
    assert build_templates(tickets, 12, 4, "korpus", BUILT_ON).digests == []


def test_a_fragment_repeated_in_one_thread_counts_once() -> None:
    """Sprawdza, czy wątek, w którym ten sam fragment stoi w opisie i w komentarzu, nie robi
    z niego szablonu przy progu 2 wątków.

    Wyłapuje liczenie wystąpień zamiast wątków: cytat w jednej sprawie stawałby się szablonem
    i znikał przy pierwszym wystąpieniu, czyli razem z oryginalną wiadomością."""
    ticket = mail_ticket(FOOTER, [("klient", f"> {FOOTER}")])

    assert build_templates([ticket], 12, 2, "korpus", BUILT_ON).digests == []


def test_image_references_do_not_enter_the_fragments() -> None:
    """Sprawdza, czy fragment przerwany odwołaniem do obrazka (`[cid:…]`, inne w każdym mailu)
    jest szablonem tak samo jak bez niego.

    Wyłapuje słownik liczony z surowej treści zamiast z treści, którą czyści normalizer: logo
    w stopce rozbijałoby jej fragmenty i stopka nie weszłaby do słownika."""
    tickets = [
        mail_ticket(f"Ta wiadomość [cid:image00{number}.png@01DCF2C1] i jej załączniki są poufne "
                    "i przeznaczone wyłącznie dla wskazanego odbiorcy.")
        for number in range(2)
    ]

    templates = build_templates(tickets, 12, 2, "korpus", BUILT_ON)

    assert run_digest(words_of(FOOTER)[:12]) in templates.digests
