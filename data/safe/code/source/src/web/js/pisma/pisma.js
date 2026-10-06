// Handlery modułu pism; wołane przez APP.zdarzenia po kliknięciu elementu z data-akcja="pisma/...".
APP.pisma = {
    zapiszHandler: function (parametry) {
        $.post('/pisma/zapisz', { id: parametry.id }).done(function (wynik) {
            $('#numer-pisma').text(wynik.numer);
        });
    },

    wyslijHandler: function (parametry) {
        $.post('/pisma/wyslij', { id: parametry.id }).done(function (wynik) {
            if (wynik.status === 'nieok') {
                APP.zdarzenia.wywolaj('okna/pokazBlad', { tresc: wynik.msg });
                return;
            }
            $('#status-wysylki').text(wynik.status_wysylki);
        });
    }
};
