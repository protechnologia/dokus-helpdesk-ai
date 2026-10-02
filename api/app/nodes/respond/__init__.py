"""
Description:
Węzeł `respond`: zamienia ostatnią odpowiedź modelu na model wyjścia grafu (Verdict,
propozycja, karta zgłoszenia, tekst) — z jednym retry przy błędzie walidacji — i egzekwuje
`requires_hits`: graf, który wymaga źródeł, bez źródeł nie oddaje propozycji (zasada 9).

Status: katalog. Atrapa w p. 4, właściwy węzeł w p. 7 (CLAUDE.md -> „Plan i TODO").
"""
