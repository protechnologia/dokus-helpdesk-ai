<?php

namespace Urzad\Sesja;

/**
 * Filtr żądań: sprawdza, czy sesja użytkownika jeszcze trwa.
 */
class KontrolaSesji
{
    const CZAS_ZYCIA_MINUTY = 30;

    /**
     * Zwraca true, gdy od ostatniego żądania minęło więcej niż CZAS_ZYCIA_MINUTY. Żądanie AJAX
     * dostaje wtedy status 401, a stronę logowania pokazuje dopiero przeglądarka.
     */
    public function czyWygasla($ostatnieZadanie, $teraz)
    {
        return ($teraz - $ostatnieZadanie) > self::CZAS_ZYCIA_MINUTY * 60;
    }
}
