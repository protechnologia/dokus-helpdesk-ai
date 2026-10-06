<?php

/**
 * Akcje modułu spraw: lista, zapis i słowniki używane przez listę.
 */
class sprawyActions extends sfActions
{
    /**
     * Lista spraw stanowiska. Sprawa jest widoczna tylko w okresie ważności komórki, do której
     * należy; po jego końcu znika z listy, choć nikt jej nie usunął.
     */
    public function executeLista(sfWebRequest $request)
    {
        $dzis   = date('Y-m-d');
        $sprawy = SprawaTable::getInstance()->pobierzWidoczne($this->getUser()->getStanowiskoId(), $dzis);

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $sprawy)));
    }

    /**
     * Zapisuje sprawę. Znak sprawy powstaje raz, przy pierwszym zapisie.
     */
    public function executeZapisz(sfWebRequest $request)
    {
        $sprawa = SprawaTable::getInstance()->find($request->getParameter('id'));
        if (!$sprawa) {
            return $this->renderText(json_encode(array('status' => 'nieok', 'msg' => 'Nie znaleziono sprawy')));
        }
        $sprawa->temat = $request->getParameter('temat');
        $sprawa->save();

        return $this->renderText(json_encode(array('status' => 'ok')));
    }

    /**
     * Zwraca słownik „kategorie" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikKategorie(sfWebRequest $request)
    {
        $wiersze = SprawaKategorieTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „statusy" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikStatusy(sfWebRequest $request)
    {
        $wiersze = SprawaStatusyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „priorytety" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikPriorytety(sfWebRequest $request)
    {
        $wiersze = SprawaPriorytetyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „terminy" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikTerminy(sfWebRequest $request)
    {
        $wiersze = SprawaTerminyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „etykiety" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikEtykiety(sfWebRequest $request)
    {
        $wiersze = SprawaEtykietyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „wydzialy" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikWydzialy(sfWebRequest $request)
    {
        $wiersze = SprawaWydzialyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „referenci" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikReferenci(sfWebRequest $request)
    {
        $wiersze = SprawaReferenciTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „rejestry" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikRejestry(sfWebRequest $request)
    {
        $wiersze = SprawaRejestryTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „teczki" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikTeczki(sfWebRequest $request)
    {
        $wiersze = SprawaTeczkiTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „uwagi" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikUwagi(sfWebRequest $request)
    {
        $wiersze = SprawaUwagiTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „notatki" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikNotatki(sfWebRequest $request)
    {
        $wiersze = SprawaNotatkiTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „zalaczniki" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikZalaczniki(sfWebRequest $request)
    {
        $wiersze = SprawaZalacznikiTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „powiazania" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikPowiazania(sfWebRequest $request)
    {
        $wiersze = SprawaPowiazaniaTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „historia" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikHistoria(sfWebRequest $request)
    {
        $wiersze = SprawaHistoriaTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „uczestnicy" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikUczestnicy(sfWebRequest $request)
    {
        $wiersze = SprawaUczestnicyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „zastepstwa" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikZastepstwa(sfWebRequest $request)
    {
        $wiersze = SprawaZastepstwaTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „akceptacje" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikAkceptacje(sfWebRequest $request)
    {
        $wiersze = SprawaAkceptacjeTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „dekretacje" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikDekretacje(sfWebRequest $request)
    {
        $wiersze = SprawaDekretacjeTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „przypomnienia" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikPrzypomnienia(sfWebRequest $request)
    {
        $wiersze = SprawaPrzypomnieniaTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „szablony" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikSzablony(sfWebRequest $request)
    {
        $wiersze = SprawaSzablonyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „podpisy" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikPodpisy(sfWebRequest $request)
    {
        $wiersze = SprawaPodpisyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „wydruki" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikWydruki(sfWebRequest $request)
    {
        $wiersze = SprawaWydrukiTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „eksporty" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikEksporty(sfWebRequest $request)
    {
        $wiersze = SprawaEksportyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „importy" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikImporty(sfWebRequest $request)
    {
        $wiersze = SprawaImportyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „filtry" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikFiltry(sfWebRequest $request)
    {
        $wiersze = SprawaFiltryTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „kolumny" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikKolumny(sfWebRequest $request)
    {
        $wiersze = SprawaKolumnyTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „widoki" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikWidoki(sfWebRequest $request)
    {
        $wiersze = SprawaWidokiTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zwraca słownik „uprawnienia" dla listy spraw, w kolejności ustawionej przez administratora.
     */
    public function executeSlownikUprawnienia(sfWebRequest $request)
    {
        $wiersze = SprawaUprawnieniaTable::getInstance()->pobierzAktywne($this->getUser()->getStanowiskoId());
        $wynik   = array();
        foreach ($wiersze as $wiersz) {
            $wynik[] = array('id' => $wiersz->id, 'nazwa' => $wiersz->nazwa);
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'data' => $wynik)));
    }

    /**
     * Zamyka sprawę. Zamkniętej sprawy nie da się otworzyć z poziomu listy.
     */
    public function executeZamknij(sfWebRequest $request)
    {
        $sprawa = SprawaTable::getInstance()->find($request->getParameter('id'));
        if ($sprawa->status === 'zamknieta') {
            return $this->renderText(json_encode(array('status' => 'nieok', 'msg' => 'Sprawa jest już zamknięta')));
        }
        $sprawa->status = 'zamknieta';
        $sprawa->save();

        return $this->renderText(json_encode(array('status' => 'ok')));
    }
}
