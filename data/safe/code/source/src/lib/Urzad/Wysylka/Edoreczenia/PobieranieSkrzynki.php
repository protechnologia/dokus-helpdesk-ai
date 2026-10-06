<?php

namespace Urzad\Wysylka\Edoreczenia;

/**
 * Pobiera nowe przesyłki ze skrzynki e-Doręczeń i zapisuje je jako pisma przychodzące.
 */
class PobieranieSkrzynki
{
    private $plikBlokady;
    private $limitMb;

    public function __construct($katalogRoboczy, $limitMb)
    {
        $this->plikBlokady = $katalogRoboczy . '/pobieranie.lock';
        $this->limitMb     = $limitMb;
    }

    /**
     * Zwraca liczbę pobranych przesyłek. Przebieg, który zastanie plik blokady, niczego nie
     * pobiera i nie zgłasza błędu: zakłada, że poprzedni przebieg jeszcze trwa.
     */
    public function pobierz($klient, $log)
    {
        if (file_exists($this->plikBlokady)) {
            $log->info('Pobieranie pominięte: istnieje plik blokady ' . $this->plikBlokady);

            return 0;
        }

        touch($this->plikBlokady);
        $pobrane = 0;
        foreach ($klient->listaNowych() as $przesylka) {
            // Przesyłka ponad limit przerywa cały przebieg: kolejne czekają, aż ktoś ją obsłuży.
            if ($przesylka['rozmiar_mb'] > $this->limitMb) {
                unlink($this->plikBlokady);
                throw new \RuntimeException('Przesyłka ' . $przesylka['id'] . ' przekracza limit pobierania');
            }
            $klient->pobierz($przesylka['id']);
            $pobrane++;
        }
        unlink($this->plikBlokady);

        return $pobrane;
    }
}
