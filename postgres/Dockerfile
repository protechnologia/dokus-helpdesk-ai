# Postgres z polskim słownikiem do wyszukiwania pełnotekstowego.
#
# Tag przypina wersję, digest dokładny obraz: ruchomy tag dałby przy rebuildzie inną bazę niż
# ta, na której przeszły testy. ARG przed FROM, bo oba etapy stoją na tym samym obrazie.
ARG POSTGRES_IMAGE=postgres:18.6-alpine3.24@sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873

# --- etap 1: słownik ---
FROM ${POSTGRES_IMAGE} AS dictionary

# Słownik sjp.pl w formacie Hunspella, z repozytorium LibreOffice (wydanie z 2026-05-11; licencje
# do wyboru, m.in. Apache 2.0, MPL 1.1 i CC BY 4.0). Pobierany przy budowaniu zamiast leżeć
# w repo: to 5 MB cudzych danych. Commit przypina treść, suma kontrolna ją sprawdza — podmieniony
# plik zatrzymuje budowanie, zamiast po cichu zmienić odmianę słów w indeksie.
ARG DICTIONARY_COMMIT=c78220a23be17268eb08040fdeb5f817776d520c
ADD --checksum=sha256:82973651651aa930335c865b339b98db376ca3dbf3a661b70b9eeb71fdf41dca \
    https://raw.githubusercontent.com/LibreOffice/dictionaries/${DICTIONARY_COMMIT}/pl_PL/pl_PL.aff \
    /build/src/pl_PL.aff
ADD --checksum=sha256:c0848440599eb88e5aca500418d5f389e562ec2c157b63dbe39d354658ffba49 \
    https://raw.githubusercontent.com/LibreOffice/dictionaries/${DICTIONARY_COMMIT}/pl_PL/pl_PL.dic \
    /build/src/pl_PL.dic

# Poprawki do słownika (kodowanie, przedrostek „nie-", nazwy własne) — opis w build.sh.
COPY dictionary/ /build/
RUN sh /build/build.sh /build/src /build/out /build/custom_words.txt

# --- etap 2: obraz usługi ---
FROM ${POSTGRES_IMAGE}

# Postgres szuka słowników w tsearch_data po nazwie bez rozszerzenia (`DictFile = polish`).
COPY --from=dictionary /build/out/polish.affix /build/out/polish.dict \
     /usr/local/share/postgresql/tsearch_data/

# Skrypty uruchamiane raz, przy pierwszym starcie na pustym wolumenie.
COPY initdb/ /docker-entrypoint-initdb.d/
