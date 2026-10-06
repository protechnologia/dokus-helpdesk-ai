<?php

namespace Urzad\Numeracja;

/**
 * Nadaje kolejne numery pism z sekwencji danego roku.
 */
class GeneratorNumeru
{
    /**
     * Zwraca numer w postaci „17/2026" i przesuwa sekwencję.
     */
    public function nastepnyNumer($rok)
    {
        $sekwencja = \SekwencjaNumeracjiTable::getInstance()->find($rok);
        // Sekwencję na nowy rok zakłada administrator; bez niej numeru nie da się nadać.
        if (!$sekwencja) {
            throw new BrakSekwencjiException('Brak sekwencji numeracji dla roku ' . $rok);
        }

        $numer               = $sekwencja->nastepny;
        $sekwencja->nastepny = $numer + 1;
        $sekwencja->save();

        return $numer . '/' . $rok;
    }
}
