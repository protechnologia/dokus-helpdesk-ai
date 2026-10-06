<?php

/**
 * Akcje modułu kontrahentów.
 */
class kontrahenciActions extends sfActions
{
    const MAKSYMALNA_DLUGOSC_NAZWY = 80;

    /**
     * Zapisuje kontrahenta. Nazwa dłuższa niż limit jest odrzucana, a nie przycinana.
     */
    public function executeZapisz(sfWebRequest $request)
    {
        $nazwa = trim($request->getParameter('nazwa'));
        if (mb_strlen($nazwa) > self::MAKSYMALNA_DLUGOSC_NAZWY) {
            $msg = 'Nazwa kontrahenta może mieć najwyżej ' . self::MAKSYMALNA_DLUGOSC_NAZWY . ' znaków';

            return $this->renderText(json_encode(array('status' => 'nieok', 'msg' => $msg)));
        }

        $kontrahent        = new Kontrahent();
        $kontrahent->nazwa = $nazwa;
        $kontrahent->save();

        return $this->renderText(json_encode(array('status' => 'ok', 'id' => $kontrahent->id)));
    }
}
