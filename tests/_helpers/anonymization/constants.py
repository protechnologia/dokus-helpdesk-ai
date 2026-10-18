"""
Description:
Stałe testów anonimizacji: zmyślone zgłoszenie z danymi osobowymi, jego postać po anonimizacji
i to, czego nie wolno znaleźć w logach ani w komunikatach błędów.
"""

# Zmyślone zgłoszenie z danymi osobowymi — to, co usługa `anonymizer` dostaje od `api`.
RAW_TEXT = "Jan Nowak z UG Zalesie, tel. 600 123 456, zgłasza, że przesyłki nie przychodzą."

# To samo zgłoszenie po anonimizacji znacznikami rodzaju (CLAUDE.md -> „Plan", p. 19).
ANONYMIZED_TEXT = (
    "{IMIĘ} {NAZWISKO} z UG Zalesie, tel. {TELEFON}, zgłasza, że przesyłki nie przychodzą."
)

# Fragmenty danych osobowych z `RAW_TEXT`: żaden nie może trafić do logu ani do komunikatu błędu.
SENSITIVE = (
    "Nowak",
    "600 123 456",
)

# Adres usługi, z którym test buduje klienta; atrapa transportu i tak nie wychodzi z procesu.
BASE_URL = "http://anonymizer:8000"

# Nazwa silnika innego niż atrapa w odpowiedziach testowych. Prawdziwego silnika jeszcze nie ma
# (p. 19.5), więc to tylko nazwa, której klient nie odrzuca.
REAL_ENGINE = "patterns"

# Nazwa atrapy silnika w odpowiedzi usługi — tę klient `api` odrzuca.
FAKE_ENGINE = "fake"
