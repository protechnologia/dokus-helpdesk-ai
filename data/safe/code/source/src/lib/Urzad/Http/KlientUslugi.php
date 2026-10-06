<?php

namespace Urzad\Http;

/**
 * Cienki klient HTTP usług zewnętrznych (skrytka, e-Doręczenia).
 */
class KlientUslugi
{
    private $adres;

    public function __construct($adres)
    {
        $this->adres = $adres;
    }

    public function wyslij($sciezka, array $dane)
    {
        $odpowiedz = @file_get_contents($this->adres . $sciezka, false, stream_context_create(array(
            'http' => array('method' => 'POST', 'content' => http_build_query($dane), 'timeout' => 20),
        )));
        if ($odpowiedz === false) {
            throw new \RuntimeException('Z serwerem usługi nie udało się skomunikować: ' . $this->adres);
        }

        return json_decode($odpowiedz, true);
    }
}
