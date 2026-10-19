import pytest

from anonymizer_app.core_patterns.email import find_email, find_email_with_at_word
from tests._helpers.patterns import Variant, replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param(find_email, "<m.kowalczyk@lipno.pl>", "<{EMAIL}>", id="w-nawiasie"),
    pytest.param(find_email, "[mailto:jan@ug.pl]", "[mailto:{EMAIL}]", id="mailto"),
    pytest.param(find_email, "na jan.nowak@ug.pl.", "na {EMAIL}.", id="kropka-na-koncu"),
    pytest.param(find_email, "kowalski.jan1980@gmail.com", "{EMAIL}", id="z-cyframi"),
    pytest.param(find_email_with_at_word, "m.kowalczyk (at) lipno.pl", "{EMAIL}", id="at"),
    pytest.param(find_email_with_at_word, "jan[at]ug.pl", "{EMAIL}", id="at-w-kwadratowym"),
    pytest.param(find_email_with_at_word, "jan {AT} ug.pl", "{EMAIL}", id="at-w-klamrowym"),
    pytest.param(find_email_with_at_word, "jan.nowak (małpa) gmail.com", "{EMAIL}", id="malpa"),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param(find_email, "konto @dokus w serwisie", id="bez-czesci-przed-malpa"),
    pytest.param(find_email, "jan@localhost", id="domena-bez-kropki"),
    pytest.param(
        find_email_with_at_word,
        "java.lang.IllegalStateException at pl.dokus.Rejestr.zapisz",
        id="slad-stosu",
    ),
    pytest.param(find_email_with_at_word, "jan at ug.pl", id="gole-at"),
]


@pytest.mark.parametrize(("variant", "text", "expected"), REPLACED)
def test_an_email_variant_replaces_the_address(variant: Variant, text: str, expected: str) -> None:
    """Sprawdza, czy warianty wzorca e-mail zamieniają na znacznik sam adres: z „@” w nawiasach
    „<…>” i „[mailto:…]”, bez kropki kończącej zdanie, oraz zapisany ze słowem „at” albo „małpa”
    w nawiasie zamiast „@”.

    Wyłapuje adres, który przechodzi przez anonimizację do modelu zewnętrznego, i zamianę, która
    zabiera nawias albo kropkę po adresie."""
    assert replaced_by(variant, text) == expected


@pytest.mark.parametrize(("variant", "text"), KEPT)
def test_an_email_variant_leaves_lookalikes(variant: Variant, text: str) -> None:
    """Sprawdza, czy warianty wzorca e-mail zostawiają napisy, które tylko przypominają adres:
    „@” bez części przed nim, domenę bez kropki, linię śladu stosu z „at” i gołe „at”.

    Wyłapuje wariant z „at”, który bierze linię śladu stosu za adres i niszczy kod błędu."""
    assert replaced_by(variant, text) == text
