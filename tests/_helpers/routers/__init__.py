"""
Description:
Trasy HTTP w testach: rozbiór strumienia SSE na zdarzenia (`sse_events()`), aplikacja z atrapami
grafów na podanym anonimizatorze i normalizerze maili (`app_on_fake_graphs()`), żądanie trasy
z jej polami dodatkowymi (`ticket_request()`), aplikacja, w której model zawodzi
w środku przebiegu `search` (`app_with_model_failing_after_tools()`), oraz próbki — stany
końcowe grafów, kroki przebiegu i żądania do tras grafów.

Logika leży w `helper.py`, próbki w `samples.py`; testy importują logikę z pakietu, a próbki
z ich modułu.
"""

from tests._helpers.routers.helper import (
    app_on_fake_graphs,
    app_with_model_failing_after_tools,
    sse_events,
    ticket_request,
)

__all__ = [
    "app_on_fake_graphs",
    "app_with_model_failing_after_tools",
    "sse_events",
    "ticket_request",
]
