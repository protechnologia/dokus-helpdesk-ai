import pytest

from anonymizer_app.core_patterns.edor import find_e_delivery_address
from tests._helpers.patterns import replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param("AE:PL-12345-67890-ABCDE-12", "{ADRES_EDOR}", id="sam-adres"),
    pytest.param("ae:pl-12345-67890-abcde-12", "{ADRES_EDOR}", id="male-litery"),
    pytest.param(
        "wysłane na adres AE:PL-48213-90517-KLMNP-07, wróciło",
        "wysłane na adres {ADRES_EDOR}, wróciło",
        id="w-zdaniu",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param("konfiguracja e-Doręczeń", id="nazwa-uslugi"),
    pytest.param("AE:PL-1234-67890-ABCDE-12", id="za-krotki-blok"),
    pytest.param("AE:PL-12345-67890-ABCDE-123", id="dluzsza-suma"),
    pytest.param("XAE:PL-12345-67890-ABCDE-12", id="sklejony-z-litera"),
]


@pytest.mark.parametrize(("text", "expected"), REPLACED)
def test_the_e_delivery_variant_replaces_the_address(text: str, expected: str) -> None:
    """Sprawdza, czy wzorzec adresu do e-Doręczeń zamienia na znacznik cały adres
    „AE:PL-00000-00000-AAAAA-00”, także pisany małymi literami i stojący w zdaniu.

    Wyłapuje adres do e-Doręczeń mieszkańca, który przechodzi przez anonimizację do modelu
    zewnętrznego; w korpusie stoi w co setnym zgłoszeniu."""
    assert replaced_by(find_e_delivery_address, text) == expected


@pytest.mark.parametrize("text", KEPT)
def test_the_e_delivery_variant_leaves_lookalikes(text: str) -> None:
    """Sprawdza, czy wzorzec adresu do e-Doręczeń zostawia nazwę usługi, adres z blokiem
    o złej długości i adres sklejony z literą przed „AE”.

    Wyłapuje wzorzec, który zamienia nazwę kanału, choć to wiedza, albo bierze za adres napis
    innego kształtu."""
    assert replaced_by(find_e_delivery_address, text) == text
