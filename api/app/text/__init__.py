# Celowo pusty i celowo NIE skasowany. Nikt nie importuje `app.text` — katalog trzyma wyłącznie
# dokumenty .md i .json — ale `[tool.setuptools.packages.find]` rozpoznaje pakiety PO tym pliku.
# Bez niego katalog nie jest pakietem, dokumenty wypadają z instalowanej dystrybucji, a loadery
# rzucają FileNotFoundError w środku przebiegu.
#
# Sprawdzone, nie założone: `find_packages(where="api")` wymienia `app.text` tylko, gdy ten plik
# istnieje. Dziś oba środowiska wybaczają jego brak — instalacja edytowalna wskazuje drzewo robocze,
# a obraz robi `COPY app/ ./app/` — i właśnie dlatego jego usunięcie zepsułoby coś gdzie indziej
# (wheel, zwykłe `pip install .`), a nie tutaj.
#
# CO TU LEŻY — dwa reżimy, które wyglądają podobnie, a nie są (CLAUDE.md -> „Prompty"):
#   * NASZE, tylko przez gita, pod testem-strażnikiem: prompt_parse_ticket_user.md
#     i prompt_parse_ticket_system.md. Ich edycja zmienia znaczenie każdego PRZYSZŁEGO artefaktu
#     w data/parsed/ (zasada 7), więc nie są wystawiane klientowi ani edytowane w runtime.
#     Prompty grafów leżą w katalogach grafów (app/graph/<graf>/), nie tutaj.
#   * DANE KLIENTA, wersjonowane polem w pliku: dict_resolution.json i domyślne zestawy reguł
#     dict_rules_<graf>.json (gate_close, gate_reply, polish). Przejmie je magazyn reguł (p. 29),
#     gdzie staną się edytowalne przez GUI.
# Katalog jest płaski, więc różnicy NIE widać w ścieżce — każdy plik mówi o swoim reżimie
# w nagłówku i tylko ten nagłówek je rozróżnia.
