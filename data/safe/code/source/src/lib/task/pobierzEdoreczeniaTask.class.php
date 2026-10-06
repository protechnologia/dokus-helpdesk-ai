<?php

/**
 * Zadanie cykliczne: pobiera przesyłki z e-Doręczeń. Uruchamiane z harmonogramu co 15 minut.
 */
class pobierzEdoreczeniaTask extends sfBaseTask
{
    protected function configure()
    {
        $this->namespace = 'edoreczenia';
        $this->name      = 'pobierz';
    }

    protected function execute($arguments = array(), $options = array())
    {
        $pobieranie = new \Urzad\Wysylka\Edoreczenia\PobieranieSkrzynki(
            sfConfig::get('sf_data_dir') . '/edoreczenia',
            sfConfig::get('app_edoreczenia_limit_zalacznika_mb')
        );
        $klient  = new \Urzad\Http\KlientUslugi(sfConfig::get('app_edoreczenia_adres_uslugi'));
        $pobrane = $pobieranie->pobierz($klient, $this->getLogger());

        $this->logSection('edoreczenia', 'Pobrano przesyłek: ' . $pobrane);
    }
}
