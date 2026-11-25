"""
Description:
Stałe zestawu bramki wysyłki na prawdziwych wiadomościach (p. 33.3): plik zestawu, wątki po
anonimizacji, z których test wycina wiadomości konsultantów, warstwy doboru, ustawienia pomiaru
na żywym modelu i jego progi.
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

# Reguły wysyłki zestawu domyślnego w wersji, pod którą oznaczano zestaw, po numerze: przepuszczenia
# liczy się osobno na każdą, bo rzadkie reguły zginęłyby w sumie.
RULES = (1, 2, 3, 4, 5, 6)

# Ile wiadomości naraz idzie do modelu, jak w pomiarze bramki zamknięcia (decyzja 2026-11-25): czas
# sprawy jest bliski czasowi jednej wysyłki na produkcji i nie trafia na limit dostawcy.
CONCURRENCY = 4

# Czas anonimizacji krótkiego tekstu na Bieliku z pomiaru z 2026-10-19 (tekst zmyślony, jedno
# żądanie naraz: średnio 1,0 s, maks. 3,8 s). Test idzie bez poda, więc raport dolicza go do czasu
# bramki, żeby czas porównać z cierpliwością UI helpdesku.
ANONYMIZATION_MEAN_SECONDS = 1.0
ANONYMIZATION_MAX_SECONDS  = 3.8

# Progi pomiaru: gorszy wynik z dwóch przebiegów na `gpt-6.1-sol`, zmierzony 2026-11-25 na regułach
# w wersji 4 bez zdania o formie bezosobowej w regule 3, które doszło po pomiarze i nie jest
# zmierzone (fałszywych alarmów 9 i 8 ze 108; na wersji 3 było 16 i 18). Fałszywe alarmy liczy się
# wśród wiadomości poprawnych, a przepuszczenia osobno na każdą regułę: wiadomość łamiąca dwie
# reguły przepuszczona liczy się przy obu. Pilnują, żeby nie było gorzej.
MAX_FALSE_ALARMS = 9
MAX_MISSES = {
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 2,
    6: 0,
}
