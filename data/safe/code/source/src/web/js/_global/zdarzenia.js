// Kliknięcie w element z atrybutem data-akcja="modul/nazwa" woła APP.modul.nazwaHandler(parametry).
// Handler jest znajdowany po nazwie, bez rejestracji; atrybuty data-* przychodzą w parametrach.
var APP = window.APP || {};

APP.zdarzenia = {
    wywolaj: function (akcja, parametry) {
        var czesci  = akcja.split('/');
        var modul   = APP[czesci[0]];
        var handler = modul ? modul[czesci[1] + 'Handler'] : null;
        if (!handler) {
            console.warn('Brak handlera dla akcji: ' + akcja);
            return;
        }
        handler(parametry || {});
    }
};

$(document).on('click', '[data-akcja]', function () {
    APP.zdarzenia.wywolaj($(this).data('akcja'), $(this).data());
});
