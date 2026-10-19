import pytest

from anonymizer_app.core_patterns.phone_number import (
    find_extension_after_label,
    find_landline,
    find_mobile,
)
from tests._helpers.patterns import Variant, replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param(find_mobile, "600 100 200", "{TELEFON}", id="komorkowy-spacje"),
    pytest.param(find_mobile, "512-345-678", "{TELEFON}", id="komorkowy-myslniki"),
    pytest.param(find_mobile, "600 100-200", "{TELEFON}", id="komorkowy-mieszane"),
    pytest.param(find_mobile, "501234567", "{TELEFON}", id="komorkowy-ciagiem"),
    pytest.param(find_mobile, "+48 512 345 678", "{TELEFON}", id="komorkowy-plus-48"),
    pytest.param(find_mobile, "0048 512345678", "{TELEFON}", id="komorkowy-0048"),
    pytest.param(find_mobile, "(+48) 600 100 200", "{TELEFON}", id="komorkowy-48-w-nawiasie"),
    pytest.param(find_mobile, "+48 600\xa0100\xa0200", "{TELEFON}", id="komorkowy-twarde-spacje"),
    pytest.param(find_mobile, "kom.694111222", "kom.{TELEFON}", id="komorkowy-sklejony"),
    pytest.param(find_landline, "81 532 10 15", "{TELEFON}", id="stacjonarny"),
    pytest.param(find_landline, "81 532-10 15", "{TELEFON}", id="stacjonarny-mieszane"),
    pytest.param(find_landline, "(22) 456 78 90", "{TELEFON}", id="stacjonarny-nawias"),
    pytest.param(find_landline, "(081) 532 10 15", "{TELEFON}", id="stacjonarny-zero"),
    pytest.param(find_landline, "+48 22 456-78-90", "{TELEFON}", id="stacjonarny-plus-48"),
    pytest.param(find_landline, "22\xa0456 78 90", "{TELEFON}", id="stacjonarny-twarda-spacja"),
    pytest.param(
        find_landline,
        "81 532 10 15 wew. 115",
        "{TELEFON}",
        id="stacjonarny-z-wewnetrznym",
    ),
    pytest.param(find_landline, "81 5321015", "{TELEFON}", id="siedem-ciagiem"),
    pytest.param(find_landline, "(22) 4567890", "{TELEFON}", id="siedem-ciagiem-nawias"),
    pytest.param(
        find_landline,
        "81 5321015w.12 , fax",
        "{TELEFON} , fax",
        id="siedem-ciagiem-z-doklejonym-wewnetrznym",
    ),
    pytest.param(find_extension_after_label, "Tel. 6013", "Tel. {TELEFON}", id="wewnetrzny-tel"),
    pytest.param(find_extension_after_label, "wew. 115", "wew. {TELEFON}", id="wewnetrzny-wew"),
    pytest.param(
        find_extension_after_label,
        "telefon: 21405",
        "telefon: {TELEFON}",
        id="wewnetrzny-telefon",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param(find_mobile, "kod ZS600100200", id="komorkowy-po-literze"),
    pytest.param(find_mobile, "numer 00659007734210852345", id="komorkowy-w-dluzszym-ciagu"),
    pytest.param(find_mobile, "60 100 200", id="komorkowy-za-krotki"),
    pytest.param(find_landline, "2026-05-12 10:14:03", id="stacjonarny-data"),
    pytest.param(find_landline, "limit 3,5 MB, paczka 1180-2026", id="stacjonarny-liczby"),
    pytest.param(find_landline, "wersja 2026 1234567", id="siedem-ciagiem-po-liczbie"),
    pytest.param(find_landline, "zamówienie 0812345678", id="dziesiec-cyfr-z-zerem"),
    pytest.param(find_extension_after_label, "tel. 12", id="wewnetrzny-za-krotki"),
    pytest.param(find_extension_after_label, "błąd 21405", id="wewnetrzny-bez-etykiety"),
    pytest.param(find_extension_after_label, "hotel 1234", id="wewnetrzny-slowo-z-tel"),
]


@pytest.mark.parametrize(("variant", "text", "expected"), REPLACED)
def test_a_phone_variant_replaces_every_notation(
    variant:  Variant,
    text:     str,
    expected: str,
) -> None:
    """Sprawdza, czy każdy wariant wzorca telefonu zamienia na znacznik numer w każdym zapisie,
    który ma łapać: komórkowy 3-3-3 albo ciągiem, stacjonarny z kierunkowym (także z zerem
    i w nawiasie) w grupach albo ciągiem, z „+48”, „0048” i „(+48)”, z odstępami mieszanymi
    i twardymi spacjami, z numerem wewnętrznym dopisanym po „wew.” albo „w.”, oraz numer
    wewnętrzny zaraz po etykiecie.

    Wyłapuje zapis telefonu, który przechodzi przez anonimizację do modelu zewnętrznego; zapisy
    z twardą spacją i z kierunkowym w nawiasie przechodziły w próbce korpusu, zanim weszły tu
    jako przypadki."""
    assert replaced_by(variant, text) == expected


@pytest.mark.parametrize(("variant", "text"), KEPT)
def test_a_phone_variant_leaves_lookalikes(variant: Variant, text: str) -> None:
    """Sprawdza, czy warianty wzorca telefonu zostawiają cyfry, które tylko wyglądają na
    telefon: kod z literami przed cyframi, dziewięć cyfr wewnątrz dłuższego ciągu, daty, liczby
    z jednostkami, numer za krótki i liczby bez etykiety telefonu.

    Wyłapuje wzorzec, który zamienia kody błędów, daty i numery przesyłek: telefon nie ma sumy
    kontrolnej, więc tylko granice numeru chronią wiedzę z wątku."""
    assert replaced_by(variant, text) == text
