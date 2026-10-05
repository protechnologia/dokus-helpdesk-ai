"""
Description:
Węzeł `respond`: ostatni krok każdego grafu. Waliduje argumenty wywołania `respond_<graf>` do
modelu wyniku grafu (werdykt, propozycja, karta zgłoszenia, tekst) i zapisuje wynik w `output`.
Odpowiedź, której nie da się przyjąć — sam tekst, odpowiedź razem z innym wywołaniem, błędne
argumenty, narzędzia wiedzy ucięte limitem tur — wraca do modelu do poprawki, jeden raz; druga
taka odpowiedź to `RespondError` i 503 z trasy. Graf, który wymaga źródeł, bez źródeł kończy bez
wyniku (zasada 9).

| plik        | co zawiera                                                                  |
|-------------|-----------------------------------------------------------------------------|
| `node.py`   | `RespondNode` — węzeł właściwy, czyta odpowiedź modelu                      |
| `fake.py`   | `FakeRespondNode` — ustawia wynik podany w konstruktorze                    |
| `base.py`   | `RespondNodeBase` — część wspólna obu: nazwa i zapis wyniku w stanie        |
| `errors.py` | `RespondError` — model nie oddał poprawnej odpowiedzi mimo poprawki         |

Węzeł dla konkretnego grafu buduje `respond_node()` z pakietu tego grafu: graf wie, czym model
odpowiada i w jakim kształcie.
"""

from app.agent_nodes.respond.errors import RespondError
from app.agent_nodes.respond.fake import FakeRespondNode
from app.agent_nodes.respond.node import MAX_RETRIES, RespondNode

__all__ = [
    "MAX_RETRIES",
    "FakeRespondNode",
    "RespondError",
    "RespondNode",
]
