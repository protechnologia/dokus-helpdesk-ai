"""
Description:
Węzeł `run_tools`: wykonuje wywołania narzędzi z ostatniej wiadomości modelu — wyłącznie tych,
które dostał, czyli dozwolonych w grafie. Argumenty waliduje klasa argumentów narzędzia; jego
wynik jako JSON wraca do `messages` jako wiadomość `tool`, a źródła z `cite()` odczytów trafiają
do `sources`. Wywołanie, którego nie da się wykonać — ponad limit swojego narzędzia, z nieznaną
nazwą, z błędnymi argumentami albo odrzucone przez samo narzędzie — dostaje w miejscu wyniku
`{"error": …}` i przebieg idzie dalej.

| plik        | co zawiera                                                                   |
|-------------|------------------------------------------------------------------------------|
| `node.py`   | `RunToolsNode` — węzeł właściwy, woła narzędzia agenta                       |
| `fake.py`   | `FakeRunToolsNode` — odpowiada ustalonym tekstem; `FakeToolAnswer`           |
| `base.py`   | `RunToolsNodeBase` — część wspólna obu: nazwa i zapis odpowiedzi w stanie    |
| `limits.py` | które wywołania są ponad limit (`AGENT_MAX_CALLS_*`) i co model wtedy czyta  |

Status: węzeł właściwy na atrapach i na prawdziwych narzędziach; fabryka grafów wpina go
w grafy z narzędziami, gdy model generujący nie jest atrapą.
"""

from app.agent_nodes.run_tools.fake import FakeRunToolsNode, FakeToolAnswer
from app.agent_nodes.run_tools.limits import calls_over_limit, limit_exceeded_text
from app.agent_nodes.run_tools.node import RunToolsNode, invalid_arguments_message

__all__ = [
    "FakeRunToolsNode",
    "FakeToolAnswer",
    "RunToolsNode",
    "calls_over_limit",
    "invalid_arguments_message",
    "limit_exceeded_text",
]
