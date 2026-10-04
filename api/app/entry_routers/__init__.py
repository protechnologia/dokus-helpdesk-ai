"""
Description:
Trasy HTTP — cienkie adaptery: żądanie → stan grafu → graf → odpowiedź, zero logiki w trasie.

Do czego:
Katalog na zasób: `router.py` z trasami i `models.py` z modelami API tylko tego zasobu. Tutaj
modele wspólne kilku tras (`models.py`: zgłoszenie, źródło, błąd) i mapowanie modeli API na
domenowe (`mapping.py`). Modele API są odrębne od domenowych (CLAUDE.md -> „Warstwy kodu").

| zasób           | trasy                                  | graf                       |
|-----------------|----------------------------------------|----------------------------|
| `health/`       | `GET /health`                          | —                          |
| `search/`       | `POST /search`                         | `search`                   |
| `gate/`         | `POST /gate/close`, `POST /gate/reply` | `gate_close`, `gate_reply` |
| `parse_ticket/` | `POST /parse-ticket`                   | `parse_ticket`             |
| `suggest/`      | `POST /suggest`, `GET /variants`       | `suggest_*` z rejestru     |
| `polish/`       | `POST /polish`                         | `polish`                   |
"""
