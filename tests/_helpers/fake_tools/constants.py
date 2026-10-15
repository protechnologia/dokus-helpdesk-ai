"""
Description:
Stałe helpera atrap narzędzi: wymiar wektora i opis projektu bez plików.
"""

# Wymiar wektora, z którym powstaje kolekcja zgłoszeń w narzędziu z padniętym embedderem.
# Kolekcja musi go dostać przy budowie, ale wartość nie ma znaczenia: wyszukanie pada na
# embedderze, zanim cokolwiek dotrze do Qdranta.
VECTOR_SIZE = 4

# Opis projektu, który oddaje atrapa `describe_code` w komplecie atrap bez materiału. Nie wymienia
# żadnego katalogu, żeby model nie szukał plików, których pozostałe atrapy kodu nie znają.
EMPTY_PROJECT_DESCRIPTION = "Zmyślona aplikacja urzędu. W tej kopii kodu nie ma żadnego pliku."
