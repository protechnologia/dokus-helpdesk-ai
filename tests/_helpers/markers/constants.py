"""
Description:
Stałe helpera znaczników: rodzaje danych, które zamienia anonimizator, placeholdery z promptów
grafów i wzór napisu w nawiasach klamrowych.
"""

import re

# Rodzaje danych, które usługa `anonymizer` zamienia na znaczniki: `KIND` wzorców
# (`anonymizer_app/core_patterns/`), `PERSON_KINDS` węzła osób i rodzaj adresu węzła adresów.
# Nowy wzorzec w usłudze to nowy wpis tutaj; inaczej jego znacznik wyjdzie jako przekręcony.
ANONYMIZATION_KINDS = {
    "IMIĘ",
    "NAZWISKO",
    "ADRES",
    "ADRES_EDOR",
    "PESEL",
    "NIP",
    "REGON",
    "KONTO",
    "DOWÓD",
    "PASZPORT",
    "TELEFON",
    "EMAIL",
}

# Placeholdery, które prompty grafów każą wstawiać za brakującą daną; wolno je dopisać, choć nie
# pochodzą od anonimizatora.
PROMPT_PLACEHOLDERS = {
    "NR_ZGŁOSZENIA",
    "NR_URZĄDZENIA",
    "DATA",
}

# Napis w nawiasach klamrowych bez odstępów: kształt znacznika i placeholdera, także przekręconego
# („{IMIENIA}", „{Nazwisko}").
BRACED = re.compile(r"\{([^{}\s]{1,30})\}")
