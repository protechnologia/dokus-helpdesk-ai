#!/bin/sh
# Składa pliki słownika dla Postgresa (`polish.affix`, `polish.dict`) ze słownika sjp.pl
# w formacie Hunspella i dokłada trzy rzeczy, bez których wyszukiwanie w zgłoszeniach myli się
# po cichu:
#
#   1. kodowanie      — źródło jest w ISO-8859-2, Postgres czyta wyłącznie UTF-8;
#   2. przedrostek    — słownik zdejmuje „nie-" (niewidoczny -> widoczny), czyli zrównuje problem
#                       z jego brakiem; reguła wypada, a zaprzeczone hasła wchodzą do słownika
#                       jako osobne słowa, więc dalej się odmieniają (niewidocznych -> niewidoczny);
#   3. nazwy własne   — słownik nie zna „eNadawcy"; `custom_words.txt` mówi, jak które słowo się
#                       odmienia, a flagi odmiany są brane z hasła-wzorca.
#
# Użycie: build.sh <katalog ze źródłem> <katalog wyjściowy> <plik z własnymi słowami>
# Każdy brak (reguły „nie-" albo hasła-wzorca) kończy budowanie obrazu błędem — cicho zbudowany
# słownik bez poprawki wyglądałby na działający.
set -eu

SRC_DIR="$1"     # np. /build/src
OUT_DIR="$2"     # np. /build/out
CUSTOM="$3"      # np. /build/custom_words.txt

mkdir -p "$OUT_DIR"

# --- 1. kodowanie ---
iconv -f ISO-8859-2 -t UTF-8 "$SRC_DIR/pl_PL.aff" > "$OUT_DIR/source.affix"
iconv -f ISO-8859-2 -t UTF-8 "$SRC_DIR/pl_PL.dic" > "$OUT_DIR/source.dict"

# --- 2. przedrostek „nie-": reguła `PFX b` wypada z afiksów ---
removed=$(grep -c -E '^PFX b ' "$OUT_DIR/source.affix" || true)
if [ "$removed" -ne 2 ]; then
    echo "build.sh: oczekiwano 2 linii reguly 'PFX b' (naglowek i przedrostek nie-), jest $removed" >&2
    exit 1
fi
grep -v -E '^PFX b ' "$OUT_DIR/source.affix" \
    | sed 's/^SET ISO8859-2$/SET UTF-8/' > "$OUT_DIR/polish.affix"

# Hasła bez flagi `b` (już nic jej nie obsługuje)...
awk -F/ '
    NF == 2 { flags = $2; gsub(/b/, "", flags); print $1 (flags == "" ? "" : "/" flags); next }
            { print }
' "$OUT_DIR/source.dict" > "$OUT_DIR/base.dict"

# ...i ich zaprzeczenia jako osobne hasła z tymi samymi flagami odmiany.
awk -F/ '
    NF == 2 && $2 ~ /b/ { flags = $2; gsub(/b/, "", flags); print "nie" $1 (flags == "" ? "" : "/" flags) }
' "$OUT_DIR/source.dict" > "$OUT_DIR/negated.dict"

# --- 3. nazwy własne: flagi odmiany z hasła-wzorca ---
: > "$OUT_DIR/custom.dict"
grep -v -E '^[[:space:]]*(#|$)' "$CUSTOM" | while read -r word pattern; do
    flags=$(grep -m 1 -E "^${pattern}/" "$OUT_DIR/source.dict" | cut -d/ -f2 | tr -d 'b')
    if [ -z "$flags" ]; then
        echo "build.sh: brak hasla-wzorca '$pattern' dla slowa '$word'" >&2
        exit 1
    fi
    echo "${word}/${flags}" >> "$OUT_DIR/custom.dict"
done

cat "$OUT_DIR/base.dict" "$OUT_DIR/negated.dict" "$OUT_DIR/custom.dict" > "$OUT_DIR/polish.dict"

echo "build.sh: hasel $(wc -l < "$OUT_DIR/polish.dict")," \
     "w tym zaprzeczonych $(wc -l < "$OUT_DIR/negated.dict")," \
     "wlasnych $(wc -l < "$OUT_DIR/custom.dict")"
