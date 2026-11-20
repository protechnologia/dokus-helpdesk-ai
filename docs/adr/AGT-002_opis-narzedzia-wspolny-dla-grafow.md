# AGT-002: Opis narzędzia dla modelu jest jeden, przy narzędziu

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-03 |
| Zastępuje | — |
| Zadanie   | commit b9a5240 |

## Kontekst

Model dostaje przy każdym narzędziu opis: jak je wywołać i co oddaje. Do 2026-10-03 każdy graf
z narzędziami miał własne opisy: 18 plików, w których różniło się jedno zdanie, a i to zdanie
mówiły już prompty systemowe grafów.

## Rozważane opcje

1. Opis w każdym grafie osobno, dopasowany do funkcji grafu — odrzucona: 18 kopii do
   poprawienia przy każdej zmianie narzędzia, choć różniły się jednym zdaniem, które należało
   do promptu grafu.
2. Jeden opis w katalogu narzędzia (`description.md`), ten sam w każdym grafie; po co wyniki
   w danej funkcji, mówi prompt grafu — wybrana.

## Decyzja

Opcja 2. Opis mówi, jak pytać narzędzie i co ono oddaje, a to nie zależy od grafu.

## Konsekwencje

### Zyski

- Jedno miejsce zmiany; opis leży obok narzędzia, jego modelu i testu kontraktu, który pilnuje
  zgodności tabelki argumentów ze schematem.

### Koszty

- Poprawka opisu zmienia wszystkie grafy naraz, więc po strojeniu jednego trzeba przemierzyć
  pozostałe (p. 23, 25–26).
