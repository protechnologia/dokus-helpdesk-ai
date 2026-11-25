# AGT-008: Zgodność przyczyn ocenia agent w uwagach, nie kod

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-11 |
| Zastępuje | — |
| Zadanie   | p. 70 (`search` jako rozpoznanie dla wdrożeniowca) |

## Kontekst

Przy jednym objawie przyczyny bywają rozłączne, a od tego, czy przeczytane sprawy zgadzają się
co do przyczyny, zależy, czy wdrożeniowiec dopyta klienta, czy odpowie. Do 2026-10-11
`respond_search` nie miał argumentów: był sygnałem końca, a wynikiem była lista źródeł
i zapytania agenta. Zwijanie zgodnych trafień wykreśliliśmy już w starej architekturze
(2026-08-19).

## Rozważane opcje

1. Sama lista źródeł — odrzucona: nie mówi, czy przeczytane sprawy zgadzają się co do
   przyczyny.
2. Ocena zgodności w kodzie — odrzucona: kod porównywałby swobodne opisy przyczyn, a przy
   103 pustych `cause` na 200 kart naiwne porównanie zamienia brak wiedzy w pewność.
3. Zwijanie zgodnych trafień w jedno — odrzucona: przy `RAG_TOP_K` = 5 licznik mierzy okno,
   nie korpus. Wraca z rozdzieleniem „ile pobrać” od „ile pokazać”, bez ponownej indeksacji.
4. Pole `zgodne` / `rozbieżne` / `nie da się ocenić` w odpowiedzi `/search` — odrzucona: za
   blisko podpowiadania guzika. Wraca, gdy helpdesk zechce pokazać zgodność jako znacznik.
5. Uwagi modelu dla wdrożeniowca obok listy źródeł — wybrana.

## Decyzja

Opcja 5. `respond_search` niesie `internal_notes`: wymagane i niepuste, w lekkim Markdownie,
w czterech sekcjach (zgłoszenia, instrukcje, kod, nie znaleziono), a w nich punkt na sprawę,
sekcję instrukcji albo fragment kodu. Jedna sprawa w jednym punkcie pokazuje zgodność albo
rozbieżność przyczyn bez czytania akapitu, a przy zerze trafień uwagi mówią, czego agent
szukał. Uwagi nie podpowiadają, czy dopytać, odpowiedzieć, czy przekazać sprawę.

## Konsekwencje

### Zyski

- Wdrożeniowiec widzi zgodność i rozbieżność przyczyn bez czytania kart.
- Lista źródeł dalej powstaje z odczytów (AGT-003), niezależnie od uwag.

### Koszty

- Uwagi pisze model, więc zasady 9 pilnuje w nich tylko prompt; kształtu kod nie sprawdza.
- Uwagi wyszły dłuższe, niż zakładał plan: 620–1770 znaków w trzech zmyślonych sprawach po
  przejściu na sekcje Markdown (pojedyncze przebiegi, nie pomiar).
