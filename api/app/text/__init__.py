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
# CO TU LEŻY: WYŁĄCZNIE DANE KLIENTA, wersjonowane polem `version` w pliku — dict_resolution.json
# i domyślne zestawy reguł dict_rules_<graf>.json (gate_close, gate_reply, polish). Przejmie je
# magazyn reguł (p. 29), gdzie staną się edytowalne przez GUI. Prompty — nasz kod, pod
# testami-strażnikami — leżą w katalogach grafów (app/agent_graphs/<graf>/), także prompt parsujący.
# Dawniej oba reżimy mieszały się tutaj i rozróżniał je tylko nagłówek pliku (CLAUDE.md ->
# „Prompty").
