"""
Description:
Stałe scenariuszy przekazania sprawy: plik zestawu, klucz metryczki, układ wiadomości z przykładu
w opisie pola `text`, obietnice działania i fragmenty tego przykładu.
"""

from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
HANDOFF_FILE = Path("data/safe/golden/handoff.json")

# Klucz metryczki zestawu: przy wczytywaniu sekcji jest pomijany, bo nie nazywa żadnego grafu.
META_KEY = "meta"

# Pierwszy i ostatni akapit wiadomości, dosłownie jak w przykładzie.
GREETING = "Dzień dobry."
FAREWELL = "Pozdrawiam."

# Najmniej akapitów: powitanie, podsumowanie, informacja o przekazaniu, pożegnanie. Więcej może
# być, bo ostrzeżenie model bywa, że daje w osobnym akapicie.
MIN_PARAGRAPHS = 4

# Rdzenie, po których przedostatni akapit rozpoznaje się jako informację o przekazaniu sprawy.
HANDOVER_WORDS = ("przekaz", "przechodzi")

# Obietnice konkretnego działania, sprawdzane w każdej sprawie: prompt ich zakazuje, a kuszą przy
# każdym przekazaniu. Bez słów o czasie, bo „w ciągu ostatnich trzech dni” bywa w podsumowaniu.
PROMISES = ("sprawdzimy", "naprawimy", "poprawimy", "zweryfikujemy", "przeanalizujemy", "wkrótce")

# Fragmenty przykładu z opisu pola `text`, sprawdzane w każdej sprawie: żadne zgłoszenie zestawu
# ich nie niesie, więc w wiadomości oznaczają treść przepisaną z przykładu.
EXAMPLE_PHRASES = ("podpis kwalifikowan", "certyfikat jest ważn")
