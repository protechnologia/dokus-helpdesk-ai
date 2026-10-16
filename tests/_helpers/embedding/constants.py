"""
Description:
Stałe testów embeddingu: nazwy modeli embeddera w odpowiedziach testowych i w punktach Qdranta.
"""

# Model, którym w testach policzono wektory punktów i zapytań. Zmyślona nazwa: testy sprawdzają,
# czy nazwa przechodzi i czy dwie różne nazwy się nie mieszają, a nie który model działa.
EMBEDDING_MODEL = "model-testowy"

# Drugi model, o tym samym wymiarze wektorów — ten, którego wektorów nie wolno mieszać z pierwszym.
OTHER_MODEL = "inny-model"
