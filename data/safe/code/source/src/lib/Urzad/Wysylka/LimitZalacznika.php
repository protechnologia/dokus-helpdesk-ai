<?php

namespace Urzad\Wysylka;

/**
 * Sprawdza rozmiar załącznika wobec limitu kanału wysyłki.
 */
class LimitZalacznika
{
    private $limitMb;

    public function __construct($limitMb)
    {
        $this->limitMb = $limitMb;
    }

    /**
     * Zwraca komunikat dla użytkownika albo null, gdy załącznik mieści się w limicie.
     */
    public function sprawdz($nazwa, $rozmiarBajty)
    {
        $rozmiarMb = round($rozmiarBajty / 1048576, 1);
        if ($rozmiarMb <= $this->limitMb) {
            return null;
        }

        return 'Załącznik ' . $nazwa . ' ma ' . $rozmiarMb . ' MB i przekracza limit ' . $this->limitMb . ' MB';
    }
}
