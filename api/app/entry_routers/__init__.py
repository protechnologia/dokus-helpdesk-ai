"""
Description:
Trasy HTTP — cienkie adaptery: żądanie → stan grafu → graf → odpowiedź, zero logiki w trasie.

Do czego:
Katalog na zasób: `router.py` z trasami, `models.py` z modelami API tylko tego zasobu
i `mapping.py`, który zamienia stan końcowy grafu na odpowiedź trasy. Tutaj modele wspólne
kilku tras (`models.py`: zgłoszenie, źródło, błąd) i mapowanie wspólne (`mapping.py`: żądanie
na zgłoszenie, źródła, zużycie, log). Modele API są odrębne od domenowych (CLAUDE.md ->
„Warstwy kodu").

| zasób           | trasy                                  | graf                       |
|-----------------|----------------------------------------|----------------------------|
| `health/`       | `GET /health`                          | —                          |
| `search/`       | `POST /search`                         | `search`                   |
| `gate/`         | `POST /gate/close`, `POST /gate/reply` | `gate_close`, `gate_reply` |
| `parse_ticket/` | `POST /parse-ticket`                   | `parse_ticket`             |
| `suggest/`      | `POST /suggest`, `GET /variants`       | `suggest_*` z rejestru     |
| `polish/`       | `POST /polish`                         | `polish`                   |
"""
