<?php

namespace Urzad\Wysylka\Epuap;

/**
 * Przekazuje pismo do skrytki adresata.
 */
class WysylkaEpuap
{
    const STATUS_W_TOKU = 'W toku';

    /**
     * Zleca wysyłkę i od razu wraca. Status „W toku" znaczy, że pismo zostało przekazane
     * i czeka na potwierdzenie; ponowne kliknięcie „Wyślij" nadaje pismo drugi raz.
     */
    public function wyslij($pismo)
    {
        $klient = new \Urzad\Http\KlientUslugi(\sfConfig::get('app_epuap_adres_uslugi'));
        $klient->wyslij('/nadaj', array('numer' => $pismo->numer));

        $pismo->status_wysylki = self::STATUS_W_TOKU;
        $pismo->save();

        return self::STATUS_W_TOKU;
    }
}
