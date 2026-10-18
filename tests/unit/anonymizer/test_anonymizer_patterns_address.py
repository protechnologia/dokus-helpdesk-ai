import pytest

from anonymizer_app.patterns.address import (
    find_address_at_postal_code,
    find_address_at_street_prefix,
)
from tests._helpers.patterns import Variant, replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param(
        find_address_at_postal_code,
        "zam. ul. Lipowa 12/4, 21-100 Lubartów, system",
        "zam. ul. {ADRES}, system",
        id="kod-z-ulica-po-ul",
    ),
    pytest.param(
        find_address_at_postal_code,
        "zam. ul. Słoneczna 7 m. 3, 05-420 Józefów",
        "zam. ul. {ADRES}",
        id="kod-numer-mieszkania-m",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Mickiewicza 20 lok. 5 00-950 Warszawa, zapis",
        "{ADRES}, zapis",
        id="kod-lok-bez-przecinka",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Polna 20 m 5, 00-950 Łódź",
        "{ADRES}",
        id="kod-mieszkanie-m-bez-kropki",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Polna 20 lok 5, 00-950 Łódź",
        "{ADRES}",
        id="kod-mieszkanie-lok-bez-kropki",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Polna 20 lok.5, 00-950 Łódź",
        "{ADRES}",
        id="kod-mieszkanie-lok-bez-spacji",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Polna 20 lokal 5, 00-950 Łódź",
        "{ADRES}",
        id="kod-mieszkanie-lokal",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Polna 20 mieszk. 5, 00-950 Łódź",
        "{ADRES}",
        id="kod-mieszkanie-mieszk",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Polna 20 mieszkanie 5, 00-950 Łódź",
        "{ADRES}",
        id="kod-mieszkanie-mieszkanie",
    ),
    pytest.param(
        find_address_at_postal_code,
        "adres Wólka 12, 08-400 Garwolin",
        "adres {ADRES}",
        id="kod-wies",
    ),
    pytest.param(
        find_address_at_postal_code,
        "(Klonowa 11a, 62-800 Kalisz)",
        "({ADRES})",
        id="kod-litera-w-numerze",
    ),
    pytest.param(
        find_address_at_postal_code,
        "ul. Jana Pawła II 5, 32-432 Pcim",
        "ul. {ADRES}",
        id="kod-ulica-od-osoby",
    ),
    pytest.param(
        find_address_at_postal_code,
        "ul.\xa0Ogrodowa\xa012, 26-600\xa0Zielona Góra",
        "ul.\xa0{ADRES}",
        id="kod-twarde-spacje-miasto-z-dwoch-slow",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "mieszka przy ul. Polnej 15, nie dostała",
        "mieszka przy ul. {ADRES}, nie dostała",
        id="ul-bez-kodu",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "Al. Róż 3/5.",
        "Al. {ADRES}.",
        id="al-wielka-litera",
    ),
    pytest.param(find_address_at_street_prefix, "ul Polnej 15", "ul {ADRES}", id="ul-bez-kropki"),
    pytest.param(
        find_address_at_street_prefix,
        "przy ulicy Polnej 15",
        "przy ulicy {ADRES}",
        id="pelne-slowo-ulicy",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "na placu Wolności 2",
        "na placu {ADRES}",
        id="pelne-slowo-placu",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "przy rondzie Daszyńskiego 1",
        "przy rondzie {ADRES}",
        id="pelne-slowo-rondzie",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "> ul. Kwiatowa 3\n",
        "> ul. {ADRES}\n",
        id="ul-w-cytacie",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "zam. ul. Leśna 9, Toruń",
        "zam. ul. {ADRES}",
        id="ul-miasto-po-przecinku",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "zam. ul. Leśna 9 Toruń",
        "zam. ul. {ADRES}",
        id="ul-miasto-bez-przecinka",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "z adresu przy al. Wyzwolenia 3/5 w Szczecinie.",
        "z adresu przy al. {ADRES}.",
        id="al-miasto-po-w",
    ),
    pytest.param(
        find_address_at_postal_code,
        "> ul. Kwiatowa 3\n> 26-600 Radom\n",
        "> ul. Kwiatowa 3\n> {ADRES}\n",
        id="kod-na-poczatku-linii-w-cytacie",
    ),
    pytest.param(
        find_address_at_postal_code,
        "Polna 5\n21-100 Lubartów",
        "Polna 5\n{ADRES}",
        id="kod-na-poczatku-linii-bez-ulicy-przed-nim",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "ul. Polna 5 KSeF odrzuca",
        "ul. {ADRES} KSeF odrzuca",
        id="ul-bez-miasta-przed-nazwa-uslugi",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "ul. Polnej 15 w sprawie decyzji",
        "ul. {ADRES} w sprawie decyzji",
        id="ul-bez-miasta-po-w",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param(
        find_address_at_postal_code,
        "wyszukiwanie po kodzie 05-400 daje pustą listę",
        id="kod-bez-miejscowosci",
    ),
    pytest.param(
        find_address_at_postal_code,
        "przy kartach 10-150 w dzienniku",
        id="liczba-w-ksztalcie-kodu",
    ),
    pytest.param(
        find_address_at_street_prefix,
        "Zgodnie z art. 5 ust. 2 pismo",
        id="artykul-i-ustep",
    ),
    pytest.param(find_address_at_street_prefix, "trafia do pok. 12", id="pokoj"),
    pytest.param(
        find_address_at_street_prefix,
        "system OS Windows 10",
        id="skrot-wielkimi-bez-kropki",
    ),
    pytest.param(find_address_at_street_prefix, "strona ug.pl Polna 5", id="skrot-w-domenie"),
    pytest.param(
        find_address_at_street_prefix,
        "Pole Ulica i numer domu jest wymagane",
        id="komunikat",
    ),
    pytest.param(
        find_address_at_postal_code,
        "10-150 kart w dzienniku",
        id="liczba-na-poczatku-linii",
    ),
    pytest.param(
        find_address_at_postal_code,
        "pismo z 21-100 Lubartów wróciło",
        id="kod-z-miejscowoscia-w-srodku-zdania",
    ),
]


@pytest.mark.parametrize(("variant", "text", "expected"), REPLACED)
def test_an_address_anchor_replaces_the_address(
    variant:  Variant,
    text:     str,
    expected: str,
) -> None:
    """Sprawdza, czy obie kotwice wzorca adresu zamieniają na znacznik adres, na który się
    rozciągają: od kodu pocztowego miejscowość w prawo, a w lewo ulica z numerem (także z numerem
    mieszkania po każdym oznaczeniu lokalu) albo początek linii; od skrótu z kropką albo bez
    niej i od pełnego słowa („ulicy”, „placu”) ulica z numerem w prawo, z miejscowością po
    przecinku, bez przecinka albo po „w”, a bez miejscowości, gdy za numerem stoi coś innego.
    Skrót, słowo przed ulicą i to, co stoi wokół adresu, zostają.

    Wyłapuje adres zamieszkania, który przechodzi przez anonimizację do modelu zewnętrznego,
    w zapisach z korpusu i z zestawu adresów z sondy."""
    assert replaced_by(variant, text) == expected


@pytest.mark.parametrize(("variant", "text"), KEPT)
def test_an_address_anchor_leaves_lookalikes(variant: Variant, text: str) -> None:
    """Sprawdza, czy kotwice wzorca adresu zostawiają to, co tylko przypomina adres: kod
    pocztowy bez miejscowości, liczbę w kształcie kodu, kod z miejscowością w środku zdania bez
    ulicy przed nim, artykuł, pokój, komunikat o polu ulicy, skrót wielkimi literami bez kropki
    („OS Windows 10”) i skrót w domenie.

    Wyłapuje wzorzec, który zamienia sygnatury, numery pokoi i komunikaty: adres nie ma sumy
    kontrolnej, więc tylko kotwica i granice chronią wiedzę z wątku."""
    assert replaced_by(variant, text) == text
