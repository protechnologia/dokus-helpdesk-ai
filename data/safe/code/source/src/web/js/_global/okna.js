// Okna modalne wspólne dla całego interfejsu.
APP.okna = {
    pokazBladHandler: function (parametry) {
        $('<div class="okno-bledu"></div>')
            .text(parametry.tresc)
            .dialog({ title: parametry.tytul || 'B\u0142\u0105d', modal: true });
    }
};
