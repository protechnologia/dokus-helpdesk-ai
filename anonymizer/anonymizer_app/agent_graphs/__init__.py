"""
Description:
Grafy usługi `anonymizer`, katalog na graf: przebieg (`graph.py`) i stan (`state.py`). Dziś jeden
graf, `anonymize/`, na którym działa silnik `agent`; jego węzły leżą w `agent_nodes/`.

Import tego pakietu wyłącza LangSmith (niżej), więc żaden graf nie ruszy z włączonym tracingiem.

| graf         | co robi                                                              |
|--------------|----------------------------------------------------------------------|
| `anonymize/` | wzorce, potem model wskazuje osoby i adresy, a kod zamienia je w tekście |
"""

import langsmith

# LangSmith zablokowany jawnie: przy LANGSMITH_TRACING=true LangGraph wysyła do chmury stan
# każdego węzła, a w tej usłudze stan to surowe zgłoszenie z danymi osobowymi. Przełącznik
# globalny wygrywa z ENV. Powielone z `api` celowo: usługi nie dzielą kodu.
langsmith.configure(enabled=False)
