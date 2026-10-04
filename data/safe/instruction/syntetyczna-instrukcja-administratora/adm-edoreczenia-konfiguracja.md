Skrzynkę e-Doręczeń konfiguruje się w Ustawienia → Integracje → e-Doręczenia. Wymagane są: adres do doręczeń elektronicznych urzędu, certyfikat systemowy i hasło do jego klucza.

Korespondencję pobiera zadanie cykliczne. Parametr „Częstotliwość pobierania” ma wartość domyślną 20 minut; operator skrzynki nie dopuszcza odpytywania częściej niż co 8 minut i przy częstszym blokuje konto na godzinę.

Gdy z e-Doręczeń nic nie przychodzi, sprawdź po kolei:

1. Datę ostatniego pobrania na karcie „Stan usługi”. Jeśli się nie zmienia, zadanie nie działa.
2. Plik blokady `edor.lock` w katalogu roboczym usługi. Zostaje po przerwanym pobieraniu i wstrzymuje kolejne; wolno go usunąć, gdy zadanie nie jest uruchomione.
3. Ważność certyfikatu. Gdy certyfikat straci ważność, w dzienniku pojawia się błąd `EDR-0417`.
4. Rozmiar oczekującej przesyłki. Przesyłka większa niż parametr „Maksymalny rozmiar przesyłki” zatrzymuje kolejkę, dopóki administrator nie pobierze jej ręcznie przyciskiem „Pobierz pominięte”.

Zmiana częstotliwości działa od następnego uruchomienia zadania. Przesyłki zaległe pobierają się wtedy same, w kolejności nadania.
