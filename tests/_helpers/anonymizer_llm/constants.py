"""
Description:
Stałe testów modelu anonimizującego usługi `anonymizer`: adres i nazwa modelu, z którymi test
buduje klienta. Atrapa transportu i tak nie wychodzi z procesu.
"""

# Adres serwera modelu w kształcie, w jakim podaje go `LLM_ANONYMIZATION_BASE_URL`: z `/v1`.
MODEL_BASE_URL = "http://model:8000/v1"

# Nazwa modelu w żądaniach testowych.
MODEL_NAME = "test-model"

# Nazwy schematów odpowiedzi węzłów z modelem — po nich atrapa rozpoznaje, o co pyta węzeł.
PERSONS_SCHEMA   = "osoby"
ADDRESSES_SCHEMA = "adresy"

# Progi testu ewaluacyjnego silnika `agent` na golden secie (p. 19.5): przecieki na rodzaj; rodzaj
# bez wpisu ma próg zero. Po przykładzie nagłówka z kilkoma adresatami, liście nazw, które nie są
# osobami, i regule odmian z Morfeuszem2 (2026-10-19) oba zestawy przeszły bez przecieku i bez
# zniszczonej wiedzy w każdym przebiegu, więc progi są zerowe. Model nie jest deterministyczny:
# czerwony test czyta się razem z przypadkami z komunikatu, zanim zmieni się próg.
AGENT_MAX_LEAKS_SAFE: dict[str, int] = {}
AGENT_MAX_LEAKS_UNSAFE: dict[str, int] = {}

# Progi zniszczonej wiedzy silnika `agent`, z tego samego pomiaru.
AGENT_MAX_DESTROYED_SAFE   = 0
AGENT_MAX_DESTROYED_UNSAFE = 0
