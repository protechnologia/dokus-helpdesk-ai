<?php

namespace Urzad\Szablony;

/**
 * Wczytuje szablony pism z katalogu `pisma` leżącego obok tej klasy.
 */
class RejestrSzablonow
{
    /** Typy pism, dla których aplikacja ma szablon. */
    private static $typy = array('decyzja', 'wezwanie', 'zawiadomienie');

    /**
     * Zwraca ścieżki szablonów według typu pisma. Katalog ma zawierać po jednym pliku na typ:
     * plik spoza listy typów zatrzymuje wczytywanie.
     */
    public function wczytaj()
    {
        $katalog  = __DIR__ . '/pisma';
        $szablony = array();

        foreach (glob($katalog . '/*.twig') as $plik) {
            $typ = basename($plik, '.twig');
            if (!in_array($typ, self::$typy)) {
                throw new \RuntimeException('W katalogu szablonów pism znajduje się nadmiarowy plik');
            }

            $szablony[$typ] = $plik;
        }

        return $szablony;
    }
}
