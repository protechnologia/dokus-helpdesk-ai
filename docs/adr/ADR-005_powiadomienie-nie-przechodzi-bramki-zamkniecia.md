# ADR-005: Powiadomienie nie przechodzi bramki zamknięcia

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-11-20 |
| Zastępuje | — |
| Zadanie   | p. 33.2 (`gate_close` na prawdziwych zamknięciach), p. 38 (wpięcie w helpdesk) |

## Kontekst

Kanał „Automat mailowy” przynosi na helpdesk wiadomości, które nie są sprawą: rozsyłkę dostawcy
(zapowiedzi aktualizacji, potwierdzenia wdrożeń, wykazy zmian), która wraca, bo skrzynka
helpdesku jest w kopii. W zamkniętych zgłoszeniach kanału to 57 ze 136, a w lipcu kanał dał 77
ze 123 nowych zgłoszeń modułu, czyli powiadomień jest kilkadziesiąt miesięcznie. Reguła 1 bramki
zamknięcia („z treści wynika, co było problemem”) nie jest w nich spełniona, a wdrożeniowiec
i tak je zamyka. Żadna reguła automatyczna nie odróżnia rozsyłki od sprawy: zgłoszenie, które
wygląda na powiadomienie, potrafi nieść najlepszą diagnozę w materiale, a przy budowie zestawu
33.2 oceniający pomylili rodzaj w 4 z 15 zgłoszeń kanału.

## Rozważane opcje

1. Zdanie w regułach klienta, że powiadomienie nie wymaga opisu problemu ani rozwiązania —
   odrzucona: bramka musiałaby rozpoznać powiadomienie, a pomyłka przepuści prawdziwą sprawę
   zamkniętą bez opisu.
2. Helpdesk nie woła bramki dla kanału mailowego — odrzucona: kanał niesie też sprawy (79 ze
   136), a powiadomień od spraw nie odróżni żadna reguła po kanale.
3. Zdanie o powiadomieniach w prompcie bramki — odrzucona: ten sam problem rozpoznania co
   w opcji 1, a do tego wyjątek od reguł klienta w naszym kodzie.
4. Bramka ocenia powiadomienie dosłownie i je blokuje; zamyka je człowiek jawnie, furtką albo
   osobną akcją helpdesku „Zamknij bez procedowania”, która nie woła bramki ani trasy
   zamknięcia; docelowo takich zgłoszeń nie ma na helpdesku — wybrana.

## Decyzja

Opcja 4, dla prostoty: reguły zostają dosłowne, a bramka nie musi rozpoznawać rodzaju
zgłoszenia. Blokada nic nie zabiera, bo powiadomienie nie niesie wiedzy do bazy: filtr jakości
odrzucił 56 z 57 powiadomień kanału.

## Konsekwencje

### Zyski

- Reguły i prompt bramki bez wyjątków.
- Sprawa, która tylko wygląda na powiadomienie, nie przejdzie bez opisu problemu i czynności.
- Zablokowane powiadomienie nie trafia do korpusu: trasa zamknięcia po blokadzie nic nie zapisuje.

### Koszty

- Dopóki helpdesk nie ma akcji „Zamknij bez procedowania”, a skrzynka helpdesku stoi w kopii
  rozsyłki, wdrożeniowiec obchodzi blokadę kilkadziesiąt razy w miesiącu, a obejście staje się
  odruchem. Dlatego jedno albo drugie to warunek wdrożenia bramki zamknięcia (p. 38).
- W pomiarze bramki oczekiwany werdykt dla powiadomienia to blokada, niezależnie od etykiet
  reguł, więc rodzaj zgłoszenia trzeba oznaczać w zestawie.

## Log

Poprawki niemerytoryczne po przyjęciu, najnowsza na górze.

- 2026-11-25 — ID GAT-001 zmienione na ADR-005: ADR-y numerujemy bez przedrostka obszaru.
