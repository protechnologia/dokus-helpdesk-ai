<?php

/**
 * Akcje modułu pism: zapis pisma i wysyłka do adresata.
 */
class pismaActions extends sfActions
{
    /**
     * Zapisuje pismo i nadaje mu numer z sekwencji bieżącego roku.
     */
    public function executeZapisz(sfWebRequest $request)
    {
        $pismo     = PismoTable::getInstance()->find($request->getParameter('id'));
        $generator = new \Urzad\Numeracja\GeneratorNumeru();

        try {
            $pismo->numer = $generator->nastepnyNumer((int) date('Y'));
            $pismo->save();
        } catch (\Urzad\Numeracja\BrakSekwencjiException $e) {
            // Odpowiedź 500 nie niesie treści wyjątku, więc przeglądarka pokazuje komunikat ogólny.
            $this->getLogger()->err($e->getMessage());
            $this->getResponse()->setStatusCode(500);

            return sfView::NONE;
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'numer' => $pismo->numer)));
    }

    /**
     * Wysyła pismo wybranym kanałem. Odpowiedź niesie status wysyłki, nie potwierdzenie doręczenia.
     */
    public function executeWyslij(sfWebRequest $request)
    {
        $pismo = PismoTable::getInstance()->find($request->getParameter('id'));
        $limit = new \Urzad\Wysylka\LimitZalacznika(sfConfig::get('app_edoreczenia_limit_zalacznika_mb'));

        foreach ($pismo->Zalaczniki as $zalacznik) {
            $blad = $limit->sprawdz($zalacznik->nazwa, $zalacznik->rozmiar);
            if ($blad !== null) {
                return $this->renderText(json_encode(array('status' => 'nieok', 'msg' => $blad)));
            }
        }

        if ($pismo->kanal_wysylki === 'epuap') {
            $wysylka = new \Urzad\Wysylka\Epuap\WysylkaEpuap();
            $status  = $wysylka->wyslij($pismo);
        } else {
            $status = 'nowe';
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'status_wysylki' => $status)));
    }
}
