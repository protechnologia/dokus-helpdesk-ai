// Archiwum działa w osobnym oknie i ma własną obsługę błędów, niezależną od głównego interfejsu.
APP.archiwum = {
    pobierzTeczkeHandler: function (parametry) {
        $.ajax({ url: '/archiwum/teczka', data: { id: parametry.id }, cichy: true })
            .done(function (wynik) {
                $('#teczka').html(wynik.html);
            })
            .fail(function () {
                APP.zdarzenia.wywolaj('okna/pokazBlad', { tresc: 'Nie udało się skomunikować z serwerem.' });
            });
    }
};
