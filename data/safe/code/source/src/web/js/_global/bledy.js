// Wspólna obsługa nieudanych żądań AJAX w głównym interfejsie.
$(document).ajaxError(function (zdarzenie, odpowiedz, ustawienia, wyjatek) {
    // Żądanie oznaczone jako ciche samo obsługuje swoje błędy.
    if (ustawienia.cichy || wyjatek === 'abort') {
        return;
    }
    if (odpowiedz.status === 401) {
        APP.zdarzenia.wywolaj('okna/pokazBlad', { tresc: 'Sesja wygas\u0142a. Zaloguj si\u0119 ponownie.' });
        return;
    }
    // Każdy inny wynik, także odpowiedź 500 z serwera, kończy się tym samym komunikatem.
    APP.zdarzenia.wywolaj('okna/pokazBlad', { tresc: 'Nie uda\u0142o si\u0119 skomunikowa\u0107 z serwerem' });
});
