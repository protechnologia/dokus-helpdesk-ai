Limity ustawia się w pliku `dokus.properties` na serwerze aplikacji. Zmiana wymaga ponownego uruchomienia usługi.

| parametr | domyślnie | znaczenie |
|---|---|---|
| `sesje_max` | 100 | liczba jednoczesnych sesji użytkowników |
| `sesja_limit_min` | 45 | po ilu minutach bezczynności sesja wygasa |
| `podpis_pamiec_mb` | 512 | pamięć dla operacji podpisu i znakowania czasem |
| `odpowiedz_limit_s` | 90 | po ilu sekundach serwer przerywa oczekiwanie na usługę zewnętrzną |
| `w_toku_alert_min` | 60 | po ilu minutach nadawania przesyłka trafia na listę ostrzeżeń |

Przekroczenie limitu czasu odpowiedzi zapisuje w dzienniku wyjątek `java.net.SocketTimeoutException`. Użytkownik dostaje wtedy ogólny komunikat o braku komunikacji z serwerem, więc przyczynę rozstrzyga dopiero dziennik.

Zbyt mała wartość `podpis_pamiec_mb` objawia się przy podpisywaniu dużych plików: operacja zatrzymuje się bez komunikatu, a w dzienniku jest wpis `PDP-118`.

Parametru `sesje_max` nie należy podnosić bez sprawdzenia pamięci serwera. Każda sesja zajmuje około 6 MB.
