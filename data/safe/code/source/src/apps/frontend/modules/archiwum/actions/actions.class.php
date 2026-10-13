<?php

/**
 * Akcje modułu archiwum. Akcje wspólne dla list, na przykład przywracanie układu kolumn, moduł
 * dziedziczy po klasie bazowej z pliku obok.
 */
class archiwumActions extends BaseArchiwumActions
{
    /**
     * Zwraca spis teczki do okna archiwum.
     */
    public function executeTeczka(sfWebRequest $request)
    {
        $teczka = TeczkaTable::getInstance()->find($request->getParameter('id'));
        if (!$teczka) {
            return $this->renderText(json_encode(array('status' => 'nieok', 'msg' => 'Nie ma takiej teczki')));
        }

        return $this->renderText(json_encode(array('status' => 'ok', 'html' => $teczka->renderujSpis())));
    }
}
