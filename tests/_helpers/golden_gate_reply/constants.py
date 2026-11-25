"""
Description:
Stałe zestawu bramki wysyłki na prawdziwych wiadomościach (p. 33.3): plik zestawu, wątki po
anonimizacji, z których test wycina wiadomości konsultantów, i warstwy doboru.
"""

from pathlib import Path

# Zestaw: wiadomości konsultantów z korpusu instancji z etykietami na każdą regułę bramki. Dane
# klienta, poza repo.
GOLDEN_FILE = Path("data/unsafe/golden/gate-reply.json")

# Wątki po anonimizacji, z których test wycina wejście bramki: ten sam tekst, który poszedł do
# modelu przy masowym imporcie.
ANONYMIZED_DIR = Path("data/unsafe/corpus/anonymized")

# Warstwy doboru w kolejności, w jakiej je losowano: wiadomość trafia do pierwszej, do której
# pasuje, więc warstwy się nie nakładają. Pierwsze trzy szukają przypadków rzadkich w korpusie,
# ostatnia mierzy fałszywe alarmy na zwykłych wiadomościach.
STRATA = ("keywords", "lowercase", "quotes", "random")

# Rola autora wiadomości, którą zestaw bierze z nagłówka komentarza: bramka ocenia to, co
# konsultant chce wysłać klientowi.
CONSULTANT_ROLE = "konsultant"
