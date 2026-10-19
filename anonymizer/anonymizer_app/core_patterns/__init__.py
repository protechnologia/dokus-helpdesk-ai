"""
Description:
Wzorce danych o stałym kształcie (p. 19.4): plik na wzorzec, a w nim osobna funkcja na każdy
wariant. Tekst przez wszystkie przepuszcza węzeł
`replace_patterns` (`agent_nodes/replace_patterns/node.py`).
Importuje się moduły wzorców (`from anonymizer_app.core_patterns import pesel`); ten plik
niczego nie eksportuje.

| moduł             | rodzaj       | sprawdzenie                                            |
|-------------------|--------------|--------------------------------------------------------|
| `pesel.py`        | `PESEL`      | suma kontrolna albo etykieta „PESEL”                   |
| `nip.py`          | `NIP`        | suma kontrolna                                         |
| `regon.py`        | `REGON`      | suma kontrolna, 9 albo 14 cyfr                         |
| `bank_account.py` | `KONTO`      | suma IBAN                                              |
| `id_card.py`      | `DOWÓD`      | cyfra kontrolna                                        |
| `passport.py`     | `PASZPORT`   | cyfra kontrolna                                        |
| `phone_number.py` | `TELEFON`    | sam kształt                                            |
| `email.py`        | `EMAIL`      | sam kształt                                            |
| `edor.py`         | `ADRES_EDOR` | sam kształt „AE:PL-…”                                  |
| `address.py`      | `ADRES`      | kotwica: kod pocztowy albo skrót lub słowo przed ulicą |

Każdy plik wzorca ma `KIND` (rodzaj, zarazem nazwa znacznika) i `VARIANTS` (funkcje wariantów
w kolejności). Wariant przyjmuje tekst i zwraca listę `Found` (`core_model/found.py`).
"""
