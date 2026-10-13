<?php

/**
 * Akcje wspólne dla list archiwum. Moduł dziedziczy je, zamiast powtarzać: klasa modułu leży
 * w pliku obok (actions.class.php) i tych akcji w nim nie widać.
 */
class BaseArchiwumActions extends sfActions
{
    /**
     * Przywraca domyślny układ kolumn listy dla zalogowanego użytkownika.
     */
    public function executeResetujUklad(sfWebRequest $request)
    {
        $lista = $request->getParameter('lista');
        $uklad = UkladListyTable::getInstance()->znajdzDlaUzytkownika($this->getUser()->getId(), $lista);
        if (!$uklad) {
            $msg = 'Lista nie ma zapisanego układu kolumn';

            return $this->renderText(json_encode(array('status' => 'nieok', 'msg' => $msg)));
        }

        $uklad->delete();

        return $this->renderText(json_encode(array('status' => 'ok')));
    }
}
