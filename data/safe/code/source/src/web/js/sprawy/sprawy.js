// Handlery modułu spraw.
APP.sprawy = {
    listaHandler: function () {
        $.get('/sprawy').done(function (wynik) {
            APP.sprawy.rysujListe(wynik.data);
        });
    },

    zapiszHandler: function (parametry) {
        $.post('/sprawy/zapisz', { id: parametry.id, temat: $('#temat-sprawy').val() }).done(function (wynik) {
            if (wynik.status === 'nieok') {
                APP.zdarzenia.wywolaj('okna/pokazBlad', { tresc: wynik.msg });
            }
        });
    },

    rysujListe: function (sprawy) {
        var lista = $('#lista-spraw').empty();
        $.each(sprawy, function (indeks, sprawa) {
            lista.append($('<li></li>').text(sprawa.znak + ' ' + sprawa.temat));
        });
    }
};
