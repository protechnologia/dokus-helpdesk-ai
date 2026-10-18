"""
Description:
Stałe testów wzorców: rodzaje danych, które zamieniają wzorce, i progi pomiaru na golden secie.
"""

# Rodzaje danych od wzorców: wszystkie rodzaje golden setu poza osobami, które wskazuje dopiero
# model (p. 19.5).
PATTERN_KINDS = (
    "PESEL",
    "NIP",
    "REGON",
    "KONTO",
    "DOWÓD",
    "PASZPORT",
    "TELEFON",
    "EMAIL",
    "ADRES_EDOR",
    "ADRES",
)

# Progi przecieków na rodzaj w zestawie zmyślonym. Wzorce są deterministyczne, więc próg to
# zmierzona liczba: każdy nowy przeciek ma dać czerwony test. Dwa adresy to znane braki: adres bez
# kotwicy i notatka małymi literami (s23, s26).
MAX_LEAKS_SAFE = {
    "PESEL":            0,
    "NIP":              0,
    "REGON":            0,
    "KONTO":            0,
    "DOWÓD":            0,
    "PASZPORT":         0,
    "TELEFON":          0,
    "EMAIL":            0,
    "ADRES_EDOR": 0,
    "ADRES":            2,
}

# Progi przecieków na rodzaj w próbce korpusu. Rodzaju, którego w próbce nie ma (konto, dowód,
# paszport), pomiar nie liczy, więc i progu nie potrzebuje.
MAX_LEAKS_UNSAFE = {
    "PESEL":   0,
    "NIP":     0,
    "REGON":   0,
    "TELEFON": 0,
    "EMAIL":   0,
    "ADRES":   0,
}
